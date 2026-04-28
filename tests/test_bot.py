"""Tests for the Discord bot client setup."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot import DiscalClient


def test_bot_has_command_tree():
    """The DiscalClient initializes with an app_commands.CommandTree."""
    client = DiscalClient()
    assert client.tree is not None
    assert isinstance(client.tree, discord.app_commands.CommandTree)


def test_bot_has_no_message_content_intent():
    """The bot uses default intents only — no privileged intents needed."""
    client = DiscalClient()
    assert not client.intents.message_content
    assert not client.intents.members
    assert not client.intents.presences


@pytest.mark.asyncio
async def test_setup_hook_registers_ping_and_syncs():
    """setup_hook registers the ping command and syncs the command tree."""
    client = DiscalClient()

    # Mock tree methods
    client.tree.add_command = MagicMock()
    client.tree.sync = AsyncMock()

    await client.setup_hook()

    client.tree.add_command.assert_called_once()
    client.tree.sync.assert_called_once()


@pytest.mark.asyncio
async def test_on_ready_logs_ready():
    """on_ready logs 'Ready' with the bot's username."""
    client = DiscalClient()

    mock_user = MagicMock()
    mock_user.name = "DiscalBot"

    with patch.object(type(client), "user", new_callable=lambda: property(lambda self: mock_user)):
        with patch.object(logging.getLogger("src.bot"), "info") as mock_log:
            await client.on_ready()
            mock_log.assert_called_once()
            fmt_string, name = mock_log.call_args[0]
            assert "Ready" in fmt_string
            assert name == "DiscalBot"
