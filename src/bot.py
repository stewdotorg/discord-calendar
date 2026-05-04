"""Discal Discord bot — main entry point and client setup."""

import logging
import os
import sys

import discord
from discord import app_commands

from src.calendar.auth import CredentialsError, load_credentials
from src.calendar.service import CalendarService
from src.commands.delete import delete  # noqa: F401  # side-effect: registers on cal group
from src.commands.list_events import cal
from src.commands.ping import ping  # noqa: F401  # side-effect: registers on cal group
from src.commands.create import create  # noqa: F401  # side-effect: registers on cal group
from src.commands.help import help_cmd  # noqa: F401  # side-effect: registers on cal group
import src.commands.settings  # noqa: F401  # side-effect: registers settings subgroup on cal
from src.commands.edit import edit  # noqa: F401  # side-effect: registers on cal group
from src.commands.rsvp import invite  # noqa: F401  # side-effect: registers on cal group
from src.commands.reminders import reminders_group, reminders_defaults_group  # noqa: F401
from src.db.queries import SettingsStore

logger = logging.getLogger(__name__)


class DiscalClient(discord.Client):
    """Discord client for the Discal calendar bot.

    Uses default intents (no privileged gateway intents needed)
    and registers slash commands via app_commands.CommandTree.
    """

    def __init__(self, db_path: str = "data/discal.db") -> None:
        intents = discord.Intents.default()
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

    async def on_ready(self) -> None:
        """Log when the bot has connected to Discord."""
        name = self.user.name if self.user else "Unknown"
        logger.info("Ready: %s", name)


def main() -> None:
    """Start the bot using the DISCORD_TOKEN environment variable."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    token = os.environ["DISCORD_TOKEN"]
    client = DiscalClient()
    client.run(token)


if __name__ == "__main__":
    main()
