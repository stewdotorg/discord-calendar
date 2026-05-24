"""Discal Discord bot — main entry point and client setup."""

import logging
import os
import sys

import discord
from discord import app_commands

from src import notify
from src.calendar.auth import CredentialsError, load_credentials
from src.calendar.service import CalendarService
from src.commands.delete import delete  # noqa: F401  # side-effect: registers on cal group
from src.commands.list_events import cal
from src.commands.ping import ping  # noqa: F401  # side-effect: registers on cal group
from src.commands.create import create  # noqa: F401  # side-effect: registers on cal group
from src.commands.help import help_cmd  # noqa: F401  # side-effect: registers on cal group
import src.commands.settings  # noqa: F401  # side-effect: registers settings subgroup on cal
from src.commands.edit import edit  # noqa: F401  # side-effect: registers on cal group
from src.commands.rsvp import (  # noqa: F401  # side-effect: registers on cal group
    RSVP_PREFIX,
    _handle_rsvp_interaction,
    invite,
)
from src.commands.reminders import reminders_group, reminders_defaults_group  # noqa: F401
from src.db.queries import SettingsStore
from src.dm_handler import handle_dm_reply

logger = logging.getLogger(__name__)


def _format_utc_timestamp() -> str:
    """Return the current UTC time as a human-readable string."""
    return discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def _is_message_content_enabled() -> bool:
    """Return True if DISCORD_ENABLE_MESSAGE_CONTENT is 'true' (case-insensitive)."""
    return os.environ.get("DISCORD_ENABLE_MESSAGE_CONTENT", "").lower() == "true"


class DiscalClient(discord.Client):
    """Discord client for the Discal calendar bot.

    The ``message_content`` privileged intent is enabled only when
    ``DISCORD_ENABLE_MESSAGE_CONTENT`` is set to ``"true"``.
    When disabled, DM reply handling, RSVP button persistence, and
    notification DMs to users are all skipped — channel notifications
    are unaffected.
    """

    def __init__(self, db_path: str = "data/discal.db") -> None:
        intents = discord.Intents.default()
        self._message_content_enabled = _is_message_content_enabled()
        if self._message_content_enabled:
            intents.message_content = True
        else:
            logger.info("message_content intent disabled — DM reply handling will be skipped")
        app_id = os.environ.get("DISCORD_APPLICATION_ID", "")
        super().__init__(intents=intents, application_id=app_id)
        self.tree = app_commands.CommandTree(self)
        self.settings = SettingsStore(db_path)

    async def setup_hook(self) -> None:
        """Register commands, verify calendar access, and sync with Discord on startup.

        The bot is guild-only — DISCORD_GUILD_ID is required, and commands are
        registered directly on the guild tree.  After the guild sync, an empty
        global sync purges any stale global /cal commands from prior deploys.
        """
        logger.info("Setting up bot...")
        guild_id = os.environ.get("DISCORD_GUILD_ID", "")
        if not guild_id:
            logger.critical("DISCORD_GUILD_ID is not set — guild-only mode requires a guild ID.")
            sys.exit(1)

        guild = discord.Object(id=int(guild_id))
        self.tree.add_command(cal, guild=guild, override=True)
        logger.info("Syncing commands to guild %s...", guild_id)
        await self.tree.sync(guild=guild)
        # Purge any stale global /cal commands left from prior deployments.
        await self.tree.sync()

        logger.info("Commands synced. Pre-warming dateparser...")
        # Pre-warm dateparser (slow first import loads language data)
        try:
            from src.utils import parse_when
            parse_when("May 1")
        except ValueError:
            pass

        # Wire tree error handler for slash-command exception notifications.
        self.tree.on_error = self._on_tree_error

        logger.info("Initializing calendar...")
        self.calendar = self._init_calendar()
        logger.info("Setup complete.")

    def _init_calendar(self) -> CalendarService | None:
        """Load service account credentials and verify calendar access.

        Returns a CalendarService on success, None when calendar env vars
        are not set, or exits the process on failure.
        """
        calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "")

        if not calendar_id:
            logger.warning(
                "Calendar not configured: GOOGLE_CALENDAR_ID is empty."
            )
            return None

        try:
            credentials = load_credentials()
        except CredentialsError as exc:
            logger.critical("Calendar auth failed: %s", exc)
            sys.exit(1)

        service = CalendarService(credentials, calendar_id)
        try:
            service.verify_access()
        except RuntimeError as exc:
            logger.critical("%s", exc)
            sys.exit(1)

        return service

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Handle persistent component interactions.

        Catches RSVP button clicks (custom_id starts with ``rsvp:``) after
        bot restarts when the in-memory View is no longer present.

        Skipped when ``DISCORD_ENABLE_MESSAGE_CONTENT`` is not ``"true"``.
        """
        if not self._message_content_enabled:
            return
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id", "")  # type: ignore[union-attr]
        if custom_id.startswith(RSVP_PREFIX):
            event_id = custom_id[len(RSVP_PREFIX):]
            await _handle_rsvp_interaction(interaction, event_id)

    async def on_ready(self) -> None:
        """Log ready, send restart notification, detect deploy, clean up invites."""
        name = self.user.name if self.user else "Unknown"
        logger.info("Ready: %s", name)

        now = _format_utc_timestamp()
        sha = notify.get_current_commit_sha() or ""
        await notify.notify(self, "restart", timestamp=now, sha=sha)
        await notify.check_and_notify_deploy(self)

        # Clean up expired pending invites on startup.
        self.settings.cleanup_expired_invites()

    async def close(self) -> None:
        """Send shutdown notification before closing the Discord connection."""
        try:
            now = _format_utc_timestamp()
            await notify.notify(self, "shutdown", timestamp=now)
        except Exception:
            logger.warning("Failed to send shutdown notification", exc_info=True)
        await super().close()

    async def on_error(self, event_method: str, /, *args, **kwargs) -> None:
        """Handle unhandled exceptions in gateway event handlers."""
        exc_type, exc_value, _ = sys.exc_info()
        message = str(exc_value) if exc_value else str(exc_type)
        # Suppress default discord.py traceback stack to avoid duplicating
        # the traceback (logged via exc_info below).
        logger.error(
            "Unhandled exception in %s: %s",
            event_method,
            message,
            exc_info=True,
        )
        try:
            await notify.notify(
                self, "error", handler=f"event:{event_method}", message=message
            )
        except Exception:
            logger.warning("Failed to send error notification", exc_info=True)

    async def _on_tree_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Handle unhandled exceptions in slash-command invocations."""
        command_name = (
            interaction.command.name
            if interaction.command
            else "unknown"
        )
        message = str(error)
        logger.error(
            "Unhandled exception in command /%s: %s",
            command_name,
            message,
            exc_info=error,
        )
        try:
            await notify.notify(
                self,
                "error",
                handler=f"command:/{command_name}",
                message=message,
            )
        except Exception:
            logger.warning("Failed to send error notification", exc_info=True)

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages for the pending-invite DM reply flow.

        Only processes DMs (guild is None).  Skips the bot's own messages.
        Delegates to ``handle_dm_reply`` for pending-invite logic.

        Catches unexpected exceptions from the reply handler so a single
        misbehaving DM cannot crash the entire message handler.
        """
        if message.author == self.user:
            return

        # Only process DMs — channel messages are ignored here.
        if message.guild is not None:
            return

        if self.calendar is None:
            return

        if not self._message_content_enabled:
            return

        try:
            await handle_dm_reply(message, self.settings, self.calendar)
        except Exception:
            logger.error(
                "Unhandled exception in handle_dm_reply for user %s",
                message.author.id,
                exc_info=True,
            )


def main() -> None:
    """Start the bot using the DISCORD_TOKEN environment variable."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    token = os.environ["DISCORD_TOKEN"]
    client = DiscalClient()
    client.run(token)


if __name__ == "__main__":
    main()
