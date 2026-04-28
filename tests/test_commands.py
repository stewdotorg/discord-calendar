"""Tests for slash command handlers."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

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


# ── /cal today ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_today_command_lists_events():
    """The /cal today command responds with an embed listing today's events."""
    from src.commands.list_events import today

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Mock the calendar service on the client
    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = [
        {
            "summary": "Team Sync",
            "start": {"dateTime": "2026-04-28T10:00:00-04:00"},
            "end": {"dateTime": "2026-04-28T11:00:00-04:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt1",
        }
    ]
    interaction.client.calendar = mock_calendar

    with patch("src.commands.list_events.get_today_eastern_range") as mock_range:
        tmin = datetime.datetime(2026, 4, 28, 4, 0, 0, tzinfo=datetime.timezone.utc)
        tmax = datetime.datetime(2026, 4, 29, 4, 0, 0, tzinfo=datetime.timezone.utc)
        mock_range.return_value = (tmin, tmax)

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await today.callback(interaction)

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax
            )

            interaction.response.send_message.assert_called_once_with(
                embed=mock_embed
            )


@pytest.mark.asyncio
async def test_today_command_calendar_not_configured():
    """The /cal today command responds with an error when calendar is not configured."""
    from src.commands.list_events import today

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await today.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "not configured" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_today_command_has_correct_metadata():
    """The today command is named 'today' under the 'cal' group."""
    from src.commands.list_events import today

    assert today.name == "today"
    assert today.description == "List today's events"
