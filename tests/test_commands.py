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
                time_min=tmin, time_max=tmax, q=None
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


# ── /cal week ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_week_command_lists_events_for_next_7_days():
    """The /cal week command lists events from today through the next 7 days."""
    from src.commands.list_events import week

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = [
        {
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-01T10:00:00-04:00"},
            "end": {"dateTime": "2026-05-01T11:00:00-04:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt1",
        }
    ]
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 8, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.get_today_eastern_range") as mock_today_range:
        mock_today_range.return_value = (tmin, tmin + datetime.timedelta(days=1))

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await week.callback(interaction)

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax, q=None
            )

            interaction.response.send_message.assert_called_once_with(
                embed=mock_embed
            )


@pytest.mark.asyncio
async def test_week_command_calendar_not_configured():
    """The /cal week command responds with an error when calendar is not configured."""
    from src.commands.list_events import week

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await week.callback(interaction)

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "not configured" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_week_command_has_correct_metadata():
    """The week command is named 'week' under the 'cal' group."""
    from src.commands.list_events import week

    assert week.name == "week"
    assert week.description == "List events for the next 7 days"


# ── /cal list ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_command_lists_events_for_date_range():
    """The /cal list command lists events in the given date range."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = [
        {
            "summary": "Team Sync",
            "start": {"dateTime": "2026-05-01T10:00:00-04:00"},
            "end": {"dateTime": "2026-05-01T11:00:00-04:00"},
            "htmlLink": "https://calendar.google.com/event?eid=evt1",
        }
    ]
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 5, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = [tmin, tmax]

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await list_events.callback(interaction, from_="2026-05-01", to="2026-05-05")

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax, q=None
            )

            interaction.response.send_message.assert_called_once_with(
                embed=mock_embed
            )


@pytest.mark.asyncio
async def test_list_command_with_search_keyword():
    """The /cal list command passes the search keyword to list_events."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = []
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 5, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = [tmin, tmax]

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_embed = MagicMock()
            mock_fmt.return_value = mock_embed

            await list_events.callback(
                interaction, from_="2026-05-01", to="2026-05-05", search="standup"
            )

            mock_calendar.list_events.assert_called_once_with(
                time_min=tmin, time_max=tmax, q="standup"
            )


@pytest.mark.asyncio
async def test_list_command_calendar_not_configured():
    """The /cal list command responds with an error when calendar is not configured."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await list_events.callback(interaction, from_="2026-05-01", to="2026-05-05")

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "not configured" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_list_command_invalid_date_returns_error():
    """The /cal list command returns a clear error for invalid date formats."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    interaction.client.calendar = mock_calendar

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = ValueError("Invalid date format")

        await list_events.callback(interaction, from_="not-a-date", to="2026-05-05")

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "Invalid date" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_list_command_has_correct_metadata():
    """The list command is named 'list' under the 'cal' group."""
    from src.commands.list_events import list_events

    assert list_events.name == "list"
    assert list_events.description == "List events in a date range"


@pytest.mark.asyncio
async def test_list_command_no_search_passes_none():
    """The /cal list command doesn't pass search when not provided."""
    from src.commands.list_events import list_events

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.list_events.return_value = []
    interaction.client.calendar = mock_calendar

    tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
    tmax = datetime.datetime(2026, 5, 5, 4, 0, 0, tzinfo=datetime.timezone.utc)

    with patch("src.commands.list_events.parse_date_eastern") as mock_parse:
        mock_parse.side_effect = [tmin, tmax]

        with patch("src.commands.list_events.format_events_embed") as mock_fmt:
            mock_fmt.return_value = MagicMock()

            await list_events.callback(interaction, from_="2026-05-01", to="2026-05-05")

            call_kwargs = mock_calendar.list_events.call_args.kwargs
            assert call_kwargs["q"] is None
