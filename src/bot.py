"""Discal Discord bot — main entry point and client setup."""

import logging
import os
import sys

import discord
from discord import app_commands

from src.calendar.auth import CredentialsError, load_credentials
from src.calendar.service import CalendarService
from src.commands.list_events import cal
from src.commands.ping import ping

logger = logging.getLogger(__name__)


class DiscalClient(discord.Client):
    """Discord client for the Discal calendar bot.

    Uses default intents (no privileged gateway intents needed)
    and registers slash commands via app_commands.CommandTree.
    """

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        """Register commands, verify calendar access, and sync with Discord on startup."""
        self.tree.add_command(ping)
        self.tree.add_command(cal)
        await self.tree.sync()

        self.calendar = self._init_calendar()

    def _init_calendar(self) -> CalendarService | None:
        """Load service account credentials and verify calendar access.

        Returns a CalendarService on success, None when calendar env vars
        are not set, or exits the process on failure.
        """
        key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
        calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "")

        if not key_path or not calendar_id:
            logger.warning(
                "Calendar not configured: GOOGLE_SERVICE_ACCOUNT_FILE "
                "or GOOGLE_CALENDAR_ID is empty."
            )
            return None

        try:
            credentials = load_credentials(key_path)
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
    token = os.environ["DISCORD_TOKEN"]
    client = DiscalClient()
    client.run(token)


if __name__ == "__main__":
    main()
