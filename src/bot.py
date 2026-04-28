"""Discal Discord bot — main entry point and client setup."""

import logging
import os

import discord
from discord import app_commands

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
        """Register commands and sync with Discord on startup."""
        self.tree.add_command(ping)
        await self.tree.sync()

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
