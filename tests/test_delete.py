"""Tests for the /cal delete command and its autocomplete callback."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from googleapiclient.errors import HttpError

from src.commands.autocomplete import event_autocomplete
from src.commands.delete import delete


# ── Autocomplete callback ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_autocomplete_filters_by_substring():
    """Autocomplete returns only events whose summary contains the typed text."""
    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup"},
        {"id": "evt2", "summary": "Design Review"},
        {"id": "evt3", "summary": "Standup Notes"},
    ]

    choices = await event_autocomplete(interaction, "standup")

    assert len(choices) == 2
    names = [c.name for c in choices]
    assert any("Team Standup" in n for n in names)
    assert any("Standup Notes" in n for n in names)
    assert not any("Design Review" in n for n in names)


@pytest.mark.asyncio
async def test_autocomplete_empty_query_returns_all():
    """Autocomplete with empty string returns all upcoming events."""
    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup"},
        {"id": "evt2", "summary": "Design Review"},
    ]

    choices = await event_autocomplete(interaction, "")

    assert len(choices) == 2


@pytest.mark.asyncio
async def test_autocomplete_no_calendar_returns_empty():
    """Autocomplete returns empty list when calendar is not configured."""
    interaction = MagicMock()
    interaction.client.calendar = None

    choices = await event_autocomplete(interaction, "test")

    assert choices == []


@pytest.mark.asyncio
async def test_autocomplete_truncates_long_titles():
    """Autocomplete truncates event summaries longer than 100 characters."""
    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    long_title = "A" * 120
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": long_title},
    ]

    choices = await event_autocomplete(interaction, "")

    assert len(choices) == 1
    assert len(choices[0].name) == 100
    assert choices[0].name.endswith("…")


@pytest.mark.asyncio
async def test_autocomplete_strips_whitespace_and_lowercases_query():
    """Autocomplete normalises the query by stripping whitespace and lowercasing."""
    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup"},
        {"id": "evt2", "summary": "Design Review"},
    ]

    choices = await event_autocomplete(interaction, "  TEAM  ")

    assert len(choices) == 1
    assert "Team Standup" in choices[0].name


# ── /cal delete command handler ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_command_metadata():
    """The delete command is named 'delete' under the 'cal' group."""
    assert delete.name == "delete"
    assert "Delete" in delete.description


@pytest.mark.asyncio
async def test_delete_command_calls_service_and_confirms():
    """The delete command calls delete_event and responds with a confirmation
    that includes the event title and date."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.delete_event.return_value = {
        "summary": "Team Standup",
        "start": "2026-05-01T14:00:00+00:00",
    }
    interaction.client.calendar = mock_calendar

    await delete.callback(interaction, event_id="abc123")

    mock_calendar.delete_event.assert_called_once_with("abc123")
    interaction.response.send_message.assert_called_once()
    response_text = interaction.response.send_message.call_args.args[0]
    assert "Team Standup" in response_text
    assert "deleted" in response_text.lower()
    # Verify the date is in Eastern time (10:00 AM ET)
    assert "10:00 AM" in response_text


@pytest.mark.asyncio
async def test_delete_command_calendar_not_configured():
    """The delete command responds with an error when calendar is not configured."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await delete.callback(interaction, event_id="abc123")

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_delete_command_formats_event_not_found_error():
    """The delete command returns a user-friendly message on 404 Not Found."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 404
    mock_calendar.delete_event.side_effect = HttpError(
        http_resp, b'{"error": "Not Found"}'
    )
    interaction.client.calendar = mock_calendar

    await delete.callback(interaction, event_id="evt")

    response_text = interaction.response.send_message.call_args.args[0]
    assert "event" in response_text.lower()


@pytest.mark.asyncio
async def test_delete_command_formats_permission_denied_error():
    """The delete command returns a user-friendly message on 403 Forbidden."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 403
    mock_calendar.delete_event.side_effect = HttpError(
        http_resp, b'{"error": "Forbidden"}'
    )
    interaction.client.calendar = mock_calendar

    await delete.callback(interaction, event_id="evt")

    response_text = interaction.response.send_message.call_args.args[0]
    assert "permission" in response_text.lower()


@pytest.mark.asyncio
async def test_delete_command_formats_generic_error():
    """The delete command returns a generic error for unexpected failures."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 500
    mock_calendar.delete_event.side_effect = HttpError(
        http_resp, b'{"error": "Server Error"}'
    )
    interaction.client.calendar = mock_calendar

    await delete.callback(interaction, event_id="evt")

    response_text = interaction.response.send_message.call_args.args[0]
    assert "failed" in response_text.lower()
