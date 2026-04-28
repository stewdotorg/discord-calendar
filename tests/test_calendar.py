"""Tests for Google Calendar auth and service modules."""

from unittest.mock import MagicMock, patch

import pytest

from src.calendar.auth import CredentialsError, load_credentials
from src.calendar.service import CalendarService


# ── auth.load_credentials ────────────────────────────────────────────────────

VALID_KEY_JSON = (
    '{"type": "service_account", "project_id": "test",'
    ' "client_email": "test@test.iam.gserviceaccount.com",'
    ' "token_uri": "https://oauth2.googleapis.com/token",'
    ' "private_key": "-----BEGIN PRIVATE KEY-----\\n'
    'MIIEugIBADANBgkqhkiG9w0BAQEFAASCBKQwggSgAgEAAoIBAQDRPTiNfUy3C1hp\\n'
    'U29KCrCIKpXNi9QlC+yGoqe4YYshM2KU98iZd1VzUmSzl3z9l3fJDwpL+I0Mzy3j\\n'
    'sqkZuK2o+l8UTmnRUUCtYMWEkUBatSqCefMLETRbZKj5WAxLgfmfHhRIyj3+PQGL\\n'
    'guBd+1GzCGY+53aqgqDGj9e68YULMm1vhN3kMFO/AQCEaNzKMc9XUFRL70xFLOIT\\n'
    'deQnL1mxuDobMv1UDeX8/CUQTlv3Z4gRI0D2AatFs6636D4ARpaXgC+TD0Wgf+5n\\n'
    't+SDIl41Wzfvsme7tuppCNenqZlSry1yikYrAuJv+2+DZivG/E+wGA7d7SCZo/ck\\n'
    'x3+O4r0xAgMBAAECgf8Bowpc08iMHbDdzpfl2kzF2jDTNqbpK6F+EFFtfb+Zlayh\\n'
    'Jg8Xgt291QqoHQPL6imxjzsrpreEdk9UM9DolWMDn2ariaZfJHvub/3Nqv73+XnO\\n'
    'cRDrPvwUTm8GwY5y5JkQBOi+JkCfpDIwShUfm/cELXLnqxMEqtA/hcNWHBobkHn6\\n'
    'QzE5FWilICeaH0WNOngLbYv1pZgamj7y9EeoIL/XP+n57hI8jKi5Oz2LOAJwgRbn\\n'
    'BHsc8SvhMaUz5uNWNbRBefbGNA76yLPd7ZzZRZa0Iw3vNCajeBaMJWqS49qvKjS1\\n'
    'cadX6zp/+T05JQtq65xdUdGVS/urdnzCtJdV8OECgYEA8K1PU1vnkYv76PFBcg62\\n'
    'pIITLZqF+wMNerER0VZNLAmh9jCrzMuRYhnySZ9HdVGefo/ic80wvo4XitFmA+UP\\n'
    'o4xUkAIFSNwVcyE0Ujnn69RaC/iBFvHlIiVF9gdW/1E+McGXNAtk8bW8JJZNi4th\\n'
    'rHR0wPcTuo2ukoY3tNKSrRECgYEA3o+E6HDTiCQ0k6i7NI5QlrHLstGiXVFGZrLB\\n'
    'E5FJ4RDDVIlrOzVTU3E2D8r/YuriK1GKEkRgJTJrcV6PogZf6/wUvxedG+mRXTfh\\n'
    'iJiY8HmoQcNwDGAqOBUlpebs/ve0hRIobkFqXcLNBgB1LO3CxEm+mTK+3UrLbOGe\\n'
    '7LpLjiECgYBuHr4m4+wmWihewtQw/a5vwtxHh2Y6HYFzW8VNRPF2bsnePRK+V34j\\n'
    'pr+HFAu8ECY2vlrcpUviRF1dNMY6jfoD2NdwNJx6Y8ikrtKjtL761mSFCaT2/KLc\\n'
    'ZrWGBoG1vFR6q5slQvli5sY471R3vsRoBbjN+b7bIqx3elXOtHJMIQKBgHb8yBP1\\n'
    'bkJVCP8AsMWSaKeIet0pkuLNNxRk8TDi9lqruaKSrY/EHL55wmuDHjLmXPDH8Ud+\\n'
    '4uBAKo07/xKi0dm6teTMXSS1JRBvddavruSyRjCSqm8TYr8FH1GpOn++MvcKFC+O\\n'
    'La3fHfndeMgCfaSvwITrSnvJJyUZIvxxRT/BAoGAPmRj3AiEv4tBZaiB/FrpPGEo\\n'
    'RPZ21slNoYt//dkTUixnqn8iXP9fxZVfg291R+D1cayx02/IHAANN1bORKieWODv\\n'
    'ln22ArhfMT13kbnqrRZpNTHb+iZKz6Z+wa/BKw2+NJqg7PQpWAAj6VSTlqzGruW9\\n'
    'FiCTRCUWN7nMpNoN4nw=\\n-----END PRIVATE KEY-----\\n"}'
)


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
    """verify_access calls calendarList.get and returns the calendar summary."""
    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_calendar_list = MagicMock()
        mock_service.calendarList.return_value = mock_calendar_list
        mock_get = MagicMock()
        mock_calendar_list.get.return_value = mock_get

        mock_get.execute.return_value = {"summary": "Team Calendar"}

        svc = CalendarService(MagicMock(), "primary")
        result = svc.verify_access()

        assert result == "Team Calendar"
        mock_calendar_list.get.assert_called_once_with(calendarId="primary")


def test_verify_access_raises_on_api_error():
    """verify_access raises an error with a descriptive message when the API call fails."""
    from googleapiclient.errors import HttpError

    with patch("src.calendar.service.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_calendar_list = MagicMock()
        mock_service.calendarList.return_value = mock_calendar_list
        mock_get = MagicMock()
        mock_calendar_list.get.return_value = mock_get

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

        from datetime import datetime, timezone

        tmin = datetime(2026, 4, 28, 4, 0, 0, tzinfo=timezone.utc)
        tmax = datetime(2026, 4, 29, 4, 0, 0, tzinfo=timezone.utc)

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

        from datetime import datetime, timezone

        svc = CalendarService(MagicMock(), "primary")
        results = svc.list_events(
            time_min=datetime(2026, 4, 28, 4, 0, 0, tzinfo=timezone.utc),
            time_max=datetime(2026, 4, 29, 4, 0, 0, tzinfo=timezone.utc),
        )

        assert results == []


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

        from datetime import datetime, timezone

        svc = CalendarService(MagicMock(), "primary")

        with pytest.raises(RuntimeError, match="Failed to list events"):
            svc.list_events(
                time_min=datetime(2026, 4, 28, 4, 0, 0, tzinfo=timezone.utc),
                time_max=datetime(2026, 4, 29, 4, 0, 0, tzinfo=timezone.utc),
            )
