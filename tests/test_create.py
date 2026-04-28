"""Tests for create command and CalendarService.create_event()."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.calendar.service import CalendarService
from src.commands.create import create


# ── CalendarService.create_event ─────────────────────────────────────────────


def test_create_event_calls_events_insert_with_correct_body():
    """create_event calls the Google Calendar events().insert() API
    with a correctly structured event body."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert

        mock_insert.execute.return_value = {
            "id": "abc123",
            "htmlLink": "https://calendar.google.com/event?eid=abc123",
        }

        svc = CalendarService(MagicMock(), "test-cal@group.calendar.google.com")
        start = datetime.datetime(2026, 5, 1, 14, 0, tzinfo=datetime.timezone.utc)

        result = svc.create_event(
            title="Team Sync",
            start=start,
            duration_minutes=60,
            description="Weekly standup",
            creator_discord_id="123456789",
        )

        assert result["id"] == "abc123"
        assert result["htmlLink"] == "https://calendar.google.com/event?eid=abc123"

        mock_events.insert.assert_called_once()
        call_args = mock_events.insert.call_args
        body = call_args.kwargs["body"]

        assert body["summary"] == "Team Sync"
        assert body["start"]["dateTime"] == "2026-05-01T14:00:00+00:00"
        assert body["start"]["timeZone"] == "UTC"
        assert body["end"]["dateTime"] == "2026-05-01T15:00:00+00:00"
        assert body["end"]["timeZone"] == "UTC"
        assert body["description"] == "Weekly standup"
        assert (
            body["extendedProperties"]["private"]["createdBy"] == "123456789"
        )


def test_create_event_defaults_duration_to_60():
    """create_event defaults duration_minutes to 60 when not specified."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert

        mock_insert.execute.return_value = {
            "id": "evt",
            "htmlLink": "https://example.com",
        }

        svc = CalendarService(MagicMock(), "cal-id")
        start = datetime.datetime(2026, 5, 1, 9, 0, tzinfo=datetime.timezone.utc)

        svc.create_event(title="Standup", start=start)

        body = mock_events.insert.call_args.kwargs["body"]
        assert body["end"]["dateTime"] == "2026-05-01T10:00:00+00:00"


def test_create_event_omits_description_when_none():
    """create_event omits the description field when not provided."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert

        mock_insert.execute.return_value = {
            "id": "evt",
            "htmlLink": "https://example.com",
        }

        svc = CalendarService(MagicMock(), "cal-id")
        start = datetime.datetime(2026, 5, 1, 9, 0, tzinfo=datetime.timezone.utc)

        svc.create_event(title="Standup", start=start)

        body = mock_events.insert.call_args.kwargs["body"]
        assert "description" not in body


def test_create_event_omits_created_by_when_none():
    """create_event omits extendedProperties when creator_discord_id is not provided."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert

        mock_insert.execute.return_value = {
            "id": "evt",
            "htmlLink": "https://example.com",
        }

        svc = CalendarService(MagicMock(), "cal-id")
        start = datetime.datetime(2026, 5, 1, 9, 0, tzinfo=datetime.timezone.utc)

        svc.create_event(title="Standup", start=start)

        body = mock_events.insert.call_args.kwargs["body"]
        assert "extendedProperties" not in body


def test_create_event_raises_on_http_error():
    """create_event re-raises HttpError so callers can handle it."""
    from googleapiclient.errors import HttpError

    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert

        http_resp = MagicMock()
        http_resp.status = 403
        http_resp.reason = "Forbidden"
        mock_insert.execute.side_effect = HttpError(
            http_resp, b'{"error": {"message": "Insufficient Permission"}}'
        )

        svc = CalendarService(MagicMock(), "cal-id")
        start = datetime.datetime(2026, 5, 1, 9, 0, tzinfo=datetime.timezone.utc)

        with pytest.raises(HttpError):
            svc.create_event(title="Blocked", start=start)


# ── /cal create command handler ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_command_has_correct_metadata():
    """The create command is named 'create' with appropriate description."""
    assert create.name == "create"
    assert "Create" in create.description


@pytest.mark.asyncio
async def test_create_command_parses_args_and_calls_service():
    """The create command parses title, date, time, duration, description
    and calls CalendarService.create_event with correct values."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    # Mock the calendar service on the interaction client
    mock_calendar = MagicMock()
    mock_calendar.create_event.return_value = {
        "id": "evt_001",
        "htmlLink": "https://calendar.google.com/event?eid=evt_001",
    }
    interaction.client.calendar = mock_calendar

    await create.callback(
        interaction,
        title="Team Sync",
        date="2026-05-01",
        time="14:00",
        duration=30,
        description="Weekly standup",
    )

    mock_calendar.create_event.assert_called_once()
    call_kwargs = mock_calendar.create_event.call_args.kwargs
    assert call_kwargs["title"] == "Team Sync"
    assert call_kwargs["duration_minutes"] == 30
    assert call_kwargs["description"] == "Weekly standup"

    # Verify the start datetime
    start = call_kwargs["start"]
    assert start.year == 2026
    assert start.month == 5
    assert start.day == 1
    assert start.hour == 14
    assert start.minute == 0
    assert start.tzinfo == datetime.timezone.utc

    # Verify creator_discord_id is passed
    assert call_kwargs["creator_discord_id"] == str(interaction.user.id)

    interaction.response.send_message.assert_called_once()
    response_text = interaction.response.send_message.call_args.args[0]
    assert "Team Sync" in response_text
    assert "2026-05-01" in response_text
    assert "14:00" in response_text
    assert "https://calendar.google.com/event?eid=evt_001" in response_text


@pytest.mark.asyncio
async def test_create_command_defaults_duration_to_60():
    """The create command defaults duration to 60 when the argument is omitted."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    mock_calendar.create_event.return_value = {
        "id": "evt_002",
        "htmlLink": "https://calendar.google.com/event?eid=evt_002",
    }
    interaction.client.calendar = mock_calendar

    await create.callback(
        interaction,
        title="Quick Sync",
        date="2026-05-02",
        time="09:00",
    )

    kwargs = mock_calendar.create_event.call_args.kwargs
    assert kwargs["duration_minutes"] == 60


@pytest.mark.asyncio
async def test_create_command_handles_no_calendar():
    """The create command responds with an error when the calendar is not configured."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.client.calendar = None

    await create.callback(
        interaction,
        title="Test",
        date="2026-05-01",
        time="12:00",
        duration=60,
        description=None,
    )

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_create_command_formats_unauthorized_error():
    """The create command returns a user-friendly message on 403 Forbidden."""
    from googleapiclient.errors import HttpError

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 403
    mock_calendar.create_event.side_effect = HttpError(
        http_resp, b'{"error": {"message": "Forbidden"}}'
    )
    interaction.client.calendar = mock_calendar

    await create.callback(
        interaction,
        title="Test",
        date="2026-05-01",
        time="12:00",
        duration=60,
        description=None,
    )

    response_text = interaction.response.send_message.call_args.args[0]
    assert "permission" in response_text.lower()


@pytest.mark.asyncio
async def test_create_command_formats_not_found_error():
    """The create command returns a user-friendly message on 404 NotFound."""
    from googleapiclient.errors import HttpError

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 404
    mock_calendar.create_event.side_effect = HttpError(
        http_resp, b'{"error": {"message": "Not Found"}}'
    )
    interaction.client.calendar = mock_calendar

    await create.callback(
        interaction,
        title="Test",
        date="2026-05-01",
        time="12:00",
        duration=60,
        description=None,
    )

    response_text = interaction.response.send_message.call_args.args[0]
    assert "not found" in response_text.lower()


@pytest.mark.asyncio
async def test_create_command_formats_rate_limit_error():
    """The create command returns a user-friendly message on 429 TooManyRequests."""
    from googleapiclient.errors import HttpError

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 429
    mock_calendar.create_event.side_effect = HttpError(
        http_resp, b'{"error": {"message": "Rate Limit Exceeded"}}'
    )
    interaction.client.calendar = mock_calendar

    await create.callback(
        interaction,
        title="Test",
        date="2026-05-01",
        time="12:00",
        duration=60,
        description=None,
    )

    response_text = interaction.response.send_message.call_args.args[0]
    assert "rate" in response_text.lower()


@pytest.mark.asyncio
async def test_create_command_formats_generic_error():
    """The create command returns a generic error message for unexpected errors."""
    from googleapiclient.errors import HttpError

    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    mock_calendar = MagicMock()
    http_resp = MagicMock()
    http_resp.status = 500
    mock_calendar.create_event.side_effect = HttpError(
        http_resp, b'{"error": {"message": "Internal Server Error"}}'
    )
    interaction.client.calendar = mock_calendar

    await create.callback(
        interaction,
        title="Test",
        date="2026-05-01",
        time="12:00",
        duration=60,
        description=None,
    )

    response_text = interaction.response.send_message.call_args.args[0]
    assert "failed" in response_text.lower() or "unexpected" in response_text.lower()
