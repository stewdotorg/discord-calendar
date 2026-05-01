"""Tests for Google Calendar auth and service modules."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.calendar.auth import CredentialsError, load_credentials
from src.calendar.service import CalendarService
from tests import VALID_KEY_JSON


# ── auth.load_credentials ────────────────────────────────────────────────────


def test_load_credentials_returns_credentials_from_json_file(tmp_path):
    """load_credentials loads a service account JSON file and returns Credentials."""
    key_file = tmp_path / "service-account.json"
    key_file.write_text(VALID_KEY_JSON)

    creds = load_credentials(str(key_file))

    assert creds is not None


def test_load_credentials_raises_on_missing_file():
    """load_credentials raises CredentialsError when the file does not exist."""
    with pytest.raises(CredentialsError, match="Service account key file not found"):
        load_credentials("./nonexistent-key.json")


def test_load_credentials_raises_on_invalid_json(tmp_path):
    """load_credentials raises CredentialsError when JSON is invalid."""
    key_file = tmp_path / "bad.json"
    key_file.write_text("not json")

    with pytest.raises(CredentialsError, match="Failed to load credentials"):
        load_credentials(str(key_file))


# ── CalendarService.verify_access ────────────────────────────────────────────


def test_verify_access_returns_summary_on_success():
    """verify_access calls calendars().get and returns the calendar summary."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_calendars = MagicMock()
        mock_service.calendars.return_value = mock_calendars
        mock_get = MagicMock()
        mock_calendars.get.return_value = mock_get

        mock_get.execute.return_value = {"summary": "Team Calendar"}

        svc = CalendarService(MagicMock(), "primary")
        result = svc.verify_access()

        assert result == "Team Calendar"
        mock_calendars.get.assert_called_once_with(calendarId="primary")


def test_verify_access_raises_on_api_error():
    """verify_access raises an error with a descriptive message when the API call fails."""
    from googleapiclient.errors import HttpError

    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_calendars = MagicMock()
        mock_service.calendars.return_value = mock_calendars
        mock_get = MagicMock()
        mock_calendars.get.return_value = mock_get

        http_resp = MagicMock()
        http_resp.status = 403
        http_resp.reason = "Forbidden"
        mock_get.execute.side_effect = HttpError(http_resp, b'{"error": "not authorized"}')

        svc = CalendarService(MagicMock(), "primary")

        with pytest.raises(RuntimeError, match="Failed to access calendar"):
            svc.verify_access()


def test_calendar_service_stores_credentials_and_calendar_id():
    """CalendarService constructor stores the credentials and calendar ID."""
    mock_creds = MagicMock()
    svc = CalendarService(mock_creds, "my-calendar@group.calendar.google.com")

    assert svc._credentials is mock_creds
    assert svc._calendar_id == "my-calendar@group.calendar.google.com"


# ── CalendarService.list_events ─────────────────────────────────────────────


def test_list_events_returns_events_for_time_range():
    """list_events calls events().list with correct timeMin/timeMax and returns results."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        mock_list = MagicMock()
        mock_events.list.return_value = mock_list

        mock_list.execute.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Team Sync",
                    "start": {"dateTime": "2026-04-28T10:00:00-04:00"},
                    "end": {"dateTime": "2026-04-28T11:00:00-04:00"},
                    "htmlLink": "https://calendar.google.com/event?eid=evt1",
                }
            ]
        }

        tmin = datetime.datetime(2026, 4, 28, 4, 0, 0, tzinfo=datetime.timezone.utc)
        tmax = datetime.datetime(2026, 4, 29, 4, 0, 0, tzinfo=datetime.timezone.utc)

        svc = CalendarService(MagicMock(), "primary")
        results = svc.list_events(time_min=tmin, time_max=tmax)

        assert len(results) == 1
        assert results[0]["summary"] == "Team Sync"

        mock_events.list.assert_called_once()
        call_kwargs = mock_events.list.call_args.kwargs
        assert call_kwargs["calendarId"] == "primary"
        assert call_kwargs["singleEvents"] is True
        assert call_kwargs["orderBy"] == "startTime"


def test_list_events_returns_empty_list_when_no_events():
    """list_events returns an empty list when there are no events in the range."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        mock_list = MagicMock()
        mock_events.list.return_value = mock_list

        mock_list.execute.return_value = {}

        svc = CalendarService(MagicMock(), "primary")
        results = svc.list_events(
            time_min=datetime.datetime(2026, 4, 28, 4, 0, 0, tzinfo=datetime.timezone.utc),
            time_max=datetime.datetime(2026, 4, 29, 4, 0, 0, tzinfo=datetime.timezone.utc),
        )

        assert results == []


def test_list_events_passes_q_parameter_to_api():
    """list_events passes the q parameter through to the Google Calendar API
    for keyword search."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        mock_list = MagicMock()
        mock_events.list.return_value = mock_list

        mock_list.execute.return_value = {"items": []}

        tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
        tmax = datetime.datetime(2026, 5, 8, 4, 0, 0, tzinfo=datetime.timezone.utc)

        svc = CalendarService(MagicMock(), "primary")
        svc.list_events(time_min=tmin, time_max=tmax, q="standup")

        call_kwargs = mock_events.list.call_args.kwargs
        assert call_kwargs["q"] == "standup"


def test_list_events_omits_q_when_none():
    """list_events does not pass q to the API when it is None."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        mock_list = MagicMock()
        mock_events.list.return_value = mock_list

        mock_list.execute.return_value = {"items": []}

        tmin = datetime.datetime(2026, 5, 1, 4, 0, 0, tzinfo=datetime.timezone.utc)
        tmax = datetime.datetime(2026, 5, 2, 4, 0, 0, tzinfo=datetime.timezone.utc)

        svc = CalendarService(MagicMock(), "primary")
        svc.list_events(time_min=tmin, time_max=tmax)

        call_kwargs = mock_events.list.call_args.kwargs
        assert "q" not in call_kwargs


def test_list_events_raises_on_api_error():
    """list_events raises RuntimeError when the API call fails."""
    from googleapiclient.errors import HttpError

    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        mock_list = MagicMock()
        mock_events.list.return_value = mock_list

        http_resp = MagicMock()
        http_resp.status = 500
        http_resp.reason = "Internal Server Error"
        mock_list.execute.side_effect = HttpError(http_resp, b'{"error": "server error"}')

        svc = CalendarService(MagicMock(), "primary")

        with pytest.raises(RuntimeError, match="Failed to list events"):
            svc.list_events(
                time_min=datetime.datetime(2026, 4, 28, 4, 0, 0, tzinfo=datetime.timezone.utc),
                time_max=datetime.datetime(2026, 4, 29, 4, 0, 0, tzinfo=datetime.timezone.utc),
            )


# ── CalendarService.delete_event ────────────────────────────────────────────


def test_delete_event_calls_events_delete_with_correct_id():
    """delete_event calls events().delete with the correct calendarId and eventId
    and returns event metadata for confirmation."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        # Mock get (to fetch event metadata before delete)
        mock_get = MagicMock()
        mock_events.get.return_value = mock_get
        mock_get.execute.return_value = {
            "summary": "Team Standup",
            "start": {"dateTime": "2026-05-01T14:00:00+00:00"},
        }

        # Mock delete
        mock_delete = MagicMock()
        mock_events.delete.return_value = mock_delete
        mock_delete.execute.return_value = None

        svc = CalendarService(MagicMock(), "test-cal@group.calendar.google.com")
        result = svc.delete_event("abc123")

        assert result == {
            "summary": "Team Standup",
            "start": "2026-05-01T14:00:00+00:00",
        }

        mock_events.get.assert_called_once_with(
            calendarId="test-cal@group.calendar.google.com", eventId="abc123"
        )
        mock_events.delete.assert_called_once_with(
            calendarId="test-cal@group.calendar.google.com", eventId="abc123"
        )


def test_delete_event_raises_on_http_error():
    """delete_event raises HttpError when the API call fails."""
    from googleapiclient.errors import HttpError

    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        mock_delete = MagicMock()
        mock_events.delete.return_value = mock_delete

        http_resp = MagicMock()
        http_resp.status = 404
        http_resp.reason = "Not Found"
        mock_delete.execute.side_effect = HttpError(
            http_resp, b'{"error": "not found"}'
        )

        svc = CalendarService(MagicMock(), "primary")

        with pytest.raises(HttpError):
            svc.delete_event("nonexistent_id")
