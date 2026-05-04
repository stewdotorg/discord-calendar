"""Tests for the /cal edit command and its autocomplete callback."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.commands.edit import (
    _compute_start_end,
    _format_confirmation,
    edit,
)


# ── _compute_start_end ──────────────────────────────────────────────────────


@patch("src.utils._dateparser_now", return_value=datetime.datetime(2026, 5, 1, 12, 0, tzinfo=datetime.timezone.utc))
def test_compute_start_end_when_only_keeps_existing_duration(_mock_now):
    """When only 'when' is provided, the existing duration is preserved."""
    current = {
        "start": {"dateTime": "2026-05-01T14:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T15:30:00+00:00"},
    }
    # "May 2 14:00" Eastern = 18:00 UTC in May (EDT)
    new_start, new_end = _compute_start_end(current, when="May 2 14:00", duration=None)

    # 2pm EDT May 2 = 18:00 UTC
    assert new_start == datetime.datetime(
        2026, 5, 2, 18, 0, tzinfo=datetime.timezone.utc
    )
    # Existing duration is 90 min
    assert new_end == datetime.datetime(
        2026, 5, 2, 19, 30, tzinfo=datetime.timezone.utc
    )


def test_compute_start_end_duration_only_keeps_existing_start():
    """When only 'duration' is provided, the existing start is preserved."""
    current = {
        "start": {"dateTime": "2026-05-01T14:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T15:00:00+00:00"},
    }
    new_start, new_end = _compute_start_end(current, when=None, duration=120)

    assert new_start == datetime.datetime(
        2026, 5, 1, 14, 0, tzinfo=datetime.timezone.utc
    )
    assert new_end == datetime.datetime(
        2026, 5, 1, 16, 0, tzinfo=datetime.timezone.utc
    )


@patch("src.utils._dateparser_now", return_value=datetime.datetime(2026, 5, 1, 12, 0, tzinfo=datetime.timezone.utc))
def test_compute_start_end_both_when_and_duration(_mock_now):
    """When both 'when' and 'duration' are provided, both are applied."""
    current = {
        "start": {"dateTime": "2026-05-01T14:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T15:00:00+00:00"},
    }
    new_start, new_end = _compute_start_end(
        current, when="May 3 10:00", duration=45
    )

    # 10am EDT May 3 = 14:00 UTC
    assert new_start == datetime.datetime(
        2026, 5, 3, 14, 0, tzinfo=datetime.timezone.utc
    )
    assert new_end == datetime.datetime(
        2026, 5, 3, 14, 45, tzinfo=datetime.timezone.utc
    )


def test_compute_start_end_raises_on_invalid_when():
    """_compute_start_end raises ValueError when 'when' is unparseable."""
    current = {
        "start": {"dateTime": "2026-05-01T14:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T15:00:00+00:00"},
    }
    with pytest.raises(ValueError):
        _compute_start_end(current, when="not a valid time", duration=None)


# ── _format_confirmation ────────────────────────────────────────────────────


def test_format_confirmation_title_changed():
    """Confirmation shows old → new title when title was changed."""
    current = {
        "summary": "Old Title",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
    }
    patch_body = {"summary": "New Title"}
    html_link = "https://calendar.google.com/event?eid=evt1"

    result = _format_confirmation(current, patch_body, html_link)

    assert "Event updated" in result
    assert "Old Title" in result
    assert "New Title" in result
    assert "→" in result
    assert html_link in result


def test_format_confirmation_time_changed():
    """Confirmation shows the updated time in Eastern."""
    current = {
        "summary": "Team Sync",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
    }
    patch_body = {
        "start": {"dateTime": "2026-05-02T19:00:00+00:00", "timeZone": "UTC"},
        "end": {"dateTime": "2026-05-02T20:00:00+00:00", "timeZone": "UTC"},
    }
    html_link = "https://calendar.google.com/event?eid=evt1"

    result = _format_confirmation(current, patch_body, html_link)

    # May 2 19:00 UTC = May 2 3:00 PM EDT
    assert "May 2, 2026 at 3:00 PM ET" in result
    assert "(60 min)" in result


def test_format_confirmation_includes_description():
    """Confirmation includes description when present."""
    current = {
        "summary": "Standup",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
    }
    patch_body = {"description": "Updated agenda"}
    html_link = "https://example.com"

    result = _format_confirmation(current, patch_body, html_link)

    assert "📝 Updated agenda" in result


# ── /cal edit command handler ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_command_metadata():
    """The edit command is named 'edit' under the 'cal' group."""
    assert edit.name == "edit"
    assert "Edit" in edit.description


@pytest.mark.asyncio
async def test_edit_no_changes_shows_current_event():
    """When no optional params are provided, the command shows the current
    event details with a 'No changes specified' message."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Team Standup",
        "start": {"dateTime": "2026-05-01T14:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T15:00:00+00:00"},
        "description": "Daily sync",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt1",
        title=None,
        when=None,
        duration=None,
        description=None,
    )

    mock_calendar.get_event.assert_called_once_with("evt1")
    mock_calendar.update_event.assert_not_called()

    interaction.edit_original_response.assert_called_once()
    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "No changes specified" in content
    assert "Team Standup" in content
    assert "Daily sync" in content


@pytest.mark.asyncio
async def test_edit_updates_title_only():
    """When only title is provided, only summary is sent in the patch."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Old Title",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    mock_calendar.update_event.return_value = {
        "id": "evt1",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt1",
        title="New Title",
        when=None,
        duration=None,
        description=None,
    )

    mock_calendar.update_event.assert_called_once()
    body = mock_calendar.update_event.call_args.kwargs
    assert body["summary"] == "New Title"
    assert "description" not in body
    assert "start" not in body
    assert "end" not in body

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Event updated" in content
    assert "Old Title" in content
    assert "New Title" in content


@patch("src.utils._dateparser_now", return_value=datetime.datetime(2026, 5, 1, 12, 0, tzinfo=datetime.timezone.utc))
@pytest.mark.asyncio
async def test_edit_updates_when_only(_mock_now):
    """When only when is provided, start and end are sent, keeping existing duration."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Team Sync",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:30:00+00:00"},
        "description": "",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    mock_calendar.update_event.return_value = {
        "id": "evt1",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt1",
        title=None,
        when="May 2 14:00",
        duration=None,
        description=None,
    )

    body = mock_calendar.update_event.call_args.kwargs
    # May 2 2pm EDT = 18:00 UTC
    assert body["start"]["dateTime"] == "2026-05-02T18:00:00+00:00"
    # Existing duration is 90 min → end at 19:30 UTC
    assert body["end"]["dateTime"] == "2026-05-02T19:30:00+00:00"
    assert "summary" not in body
    assert "description" not in body


@pytest.mark.asyncio
async def test_edit_updates_duration_only():
    """When only duration is provided, only end is sent, keeping existing start."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Team Sync",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    mock_calendar.update_event.return_value = {
        "id": "evt1",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt1",
        title=None,
        when=None,
        duration=120,
        description=None,
    )

    body = mock_calendar.update_event.call_args.kwargs
    # Start unchanged
    assert body["start"]["dateTime"] == "2026-05-01T18:00:00+00:00"
    # End shifted by 120 min
    assert body["end"]["dateTime"] == "2026-05-01T20:00:00+00:00"
    assert "summary" not in body
    assert "description" not in body


@pytest.mark.asyncio
async def test_edit_updates_description_only():
    """When only description is provided, only description is sent in the patch."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Team Sync",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    mock_calendar.update_event.return_value = {
        "id": "evt1",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt1",
        title=None,
        when=None,
        duration=None,
        description="New agenda items",
    )

    body = mock_calendar.update_event.call_args.kwargs
    assert body["description"] == "New agenda items"
    assert "summary" not in body
    assert "start" not in body
    assert "end" not in body

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "📝 New agenda items" in content


@patch("src.utils._dateparser_now", return_value=datetime.datetime(2026, 5, 1, 12, 0, tzinfo=datetime.timezone.utc))
@pytest.mark.asyncio
async def test_edit_updates_all_fields(_mock_now):
    """When all optional params are provided, all fields are sent in the patch."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Old Event",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "Old desc",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    mock_calendar.update_event.return_value = {
        "id": "evt1",
        "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt1",
        title="Brand New Event",
        when="May 3 10:00",
        duration=45,
        description="Updated description",
    )

    body = mock_calendar.update_event.call_args.kwargs
    assert body["summary"] == "Brand New Event"
    assert body["description"] == "Updated description"
    # May 3 10am EDT = 14:00 UTC
    assert body["start"]["dateTime"] == "2026-05-03T14:00:00+00:00"
    assert body["end"]["dateTime"] == "2026-05-03T14:45:00+00:00"

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Event updated" in content
    assert "Old Event" in content
    assert "Brand New Event" in content


@pytest.mark.asyncio
async def test_edit_calendar_not_configured():
    """The edit command responds with an error when calendar is not configured."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await edit.callback(
        interaction,
        event_id="evt1",
        title="New Title",
        when=None,
        duration=None,
        description=None,
    )

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_edit_invalid_when_returns_error():
    """The edit command responds with a parse error for invalid when strings."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt1",
        "summary": "Test",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
    }
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt1",
        title=None,
        when="nonsense",
        duration=None,
        description=None,
    )

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Cannot parse" in content


@pytest.mark.asyncio
async def test_edit_formats_event_not_found_on_get():
    """The edit command returns a user-friendly message when get_event returns 404."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 404
    mock_calendar.get_event.side_effect = HttpError(
        http_resp, b'{"error": "Not Found"}'
    )
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt",
        title="New Title",
        when=None,
        duration=None,
        description=None,
    )

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "not found" in content.lower() or "Event not found" in content


@pytest.mark.asyncio
async def test_edit_formats_permission_denied_on_update():
    """The edit command returns a user-friendly message when update_event returns 403."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt",
        "summary": "Test",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
    }
    http_resp = MagicMock()
    http_resp.status = 403
    mock_calendar.update_event.side_effect = HttpError(
        http_resp, b'{"error": "Forbidden"}'
    )
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt",
        title="New Title",
        when=None,
        duration=None,
        description=None,
    )

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "permission" in content.lower()


@pytest.mark.asyncio
async def test_edit_formats_generic_error_on_update():
    """The edit command returns a generic error for unexpected failures."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.get_event.return_value = {
        "id": "evt",
        "summary": "Test",
        "start": {"dateTime": "2026-05-01T18:00:00+00:00"},
        "end": {"dateTime": "2026-05-01T19:00:00+00:00"},
        "description": "",
    }
    http_resp = MagicMock()
    http_resp.status = 500
    mock_calendar.update_event.side_effect = HttpError(
        http_resp, b'{"error": "Server Error"}'
    )
    interaction.client.calendar = mock_calendar

    await edit.callback(
        interaction,
        event_id="evt",
        title="New Title",
        when=None,
        duration=None,
        description=None,
    )

    content = interaction.edit_original_response.call_args.kwargs["content"]
    assert "Failed to edit" in content or "failed" in content.lower()


@pytest.mark.asyncio
async def test_edit_command_has_autocomplete():
    """The edit command uses autocomplete on the event_id parameter."""
    from src.commands.autocomplete import event_autocomplete

    # Check that the autocomplete callback is registered on the command
    param = [
        p for p in edit._params.values()
        if p.name == "event_id"  # pyright: ignore[reportAttributeAccessIssue]
    ][0]
    assert param.autocomplete is not None  # pyright: ignore[reportAttributeAccessIssue]
    assert param.autocomplete is event_autocomplete  # pyright: ignore[reportAttributeAccessIssue]
