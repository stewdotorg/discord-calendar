"""Tests for slash command handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.ping import ping


@pytest.mark.asyncio
async def test_ping_responds_pong_ephemerally():
    """The /cal ping command responds with 'pong' as an ephemeral message."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await ping.callback(interaction)

    interaction.response.send_message.assert_called_once_with(
        "pong", ephemeral=True
    )


@pytest.mark.asyncio
async def test_ping_command_has_correct_metadata():
    """The ping command is named 'ping' with appropriate description."""
    assert ping.name == "ping"
    assert ping.description == "Ping the bot"
