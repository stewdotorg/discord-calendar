"""Tests for utility functions — embed formatting and timezone conversion."""

import datetime
from unittest.mock import MagicMock

from src.utils import (
    _format_time_range_eastern,
    format_events_embed,
    get_today_eastern_range,
)


class TestFormatDeleteError:
    """Tests for format_delete_error."""

    def test_403_maps_to_permission_denied(self):
        """format_delete_error returns permission denied message for 403."""
        from googleapiclient.errors import HttpError
        from src.utils import format_delete_error

        http_resp = MagicMock()
        http_resp.status = 403
        exc = HttpError(http_resp, b'{"error": "Forbidden"}')

        result = format_delete_error(exc)
        assert "permission" in result.lower()

    def test_404_maps_to_event_not_found(self):
        """format_delete_error returns event not found message for 404."""
        from googleapiclient.errors import HttpError
        from src.utils import format_delete_error

        http_resp = MagicMock()
        http_resp.status = 404
        exc = HttpError(http_resp, b'{"error": "Not Found"}')

        result = format_delete_error(exc)
        assert "event" in result.lower()

    def test_429_maps_to_rate_limit(self):
        """format_delete_error returns rate limit message for 429."""
        from googleapiclient.errors import HttpError
        from src.utils import format_delete_error

        http_resp = MagicMock()
        http_resp.status = 429
        exc = HttpError(http_resp, b'{"error": "Rate Limit"}')

        result = format_delete_error(exc)
        assert "rate" in result.lower()

    def test_other_status_returns_generic_error(self):
        """format_delete_error returns generic error for unexpected status."""
        from googleapiclient.errors import HttpError
        from src.utils import format_delete_error

        http_resp = MagicMock()
        http_resp.status = 500
        exc = HttpError(http_resp, b'{"error": "Server Error"}')

        result = format_delete_error(exc)
        assert "failed" in result.lower()


class TestGetTodayEasternRange:
    """Tests for get_today_eastern_range."""

    def test_returns_start_and_end_of_today_in_utc(self):
        """get_today_eastern_range returns timezone-aware UTC datetimes covering
        today in US Eastern time."""
        tmin, tmax = get_today_eastern_range()

        # Both should be timezone-aware UTC
        assert tmin.tzinfo is not None
        assert tmax.tzinfo is not None
        assert tmin.tzinfo == datetime.timezone.utc
        assert tmax.tzinfo == datetime.timezone.utc

        # tmax should be after tmin
        assert tmax > tmin

        # The span should cover approximately 24 hours
        delta = tmax - tmin
        assert delta >= datetime.timedelta(hours=23)
        assert delta <= datetime.timedelta(hours=25)


class TestFormatTimeRangeEastern:
    """Tests for _format_time_range_eastern."""

    def test_formats_same_ampm_range(self):
        """Both times in the same AM/PM period show AM/PM once."""
        result = _format_time_range_eastern(
            "2026-04-28T09:00:00-04:00",
            "2026-04-28T09:30:00-04:00",
        )
        assert result == "9:00–9:30 AM ET"

    def test_formats_cross_ampm_range(self):
        """Times crossing AM/PM show AM/PM on each."""
        result = _format_time_range_eastern(
            "2026-04-28T11:00:00-04:00",
            "2026-04-28T13:00:00-04:00",
        )
        assert result == "11:00 AM–1:00 PM ET"

    def test_formats_same_hour_pm_range(self):
        """PM range shows PM once."""
        result = _format_time_range_eastern(
            "2026-04-28T18:00:00-04:00",
            "2026-04-28T19:30:00-04:00",
        )
        assert result == "6:00–7:30 PM ET"

    def test_returns_question_mark_for_empty_strings(self):
        """Returns '?' when either time string is empty."""
        result = _format_time_range_eastern("", "2026-04-28T11:00:00-04:00")
        assert result == "?"

        result = _format_time_range_eastern("2026-04-28T10:00:00-04:00", "")
        assert result == "?"


class TestFormatEventsEmbed:
    """Tests for format_events_embed."""

    def test_empty_events_returns_no_events_embed(self):
        """format_events_embed returns an embed with 'No events' message when
        the events list is empty."""
        embed = format_events_embed([], "April 28, 2026")

        assert embed.title == "Events for April 28, 2026"
        assert embed.description == "No events scheduled for today."
        assert len(embed.fields) == 0

    def test_events_ordered_by_start_time(self):
        """format_events_embed preserves the order of events (which are
        expected to be pre-sorted by the API)."""
        events = [
            {
                "summary": "Morning Standup",
                "start": {"dateTime": "2026-04-28T09:00:00-04:00"},
                "end": {"dateTime": "2026-04-28T09:30:00-04:00"},
                "htmlLink": "https://calendar.google.com/event?eid=evt1",
            },
            {
                "summary": "Lunch",
                "start": {"dateTime": "2026-04-28T12:00:00-04:00"},
                "end": {"dateTime": "2026-04-28T13:00:00-04:00"},
                "htmlLink": "https://calendar.google.com/event?eid=evt2",
            },
        ]

        embed = format_events_embed(events, "April 28, 2026")

        assert embed.title == "Events for April 28, 2026"
        assert embed.description is None
        assert len(embed.fields) == 2

        # First event — time range display
        assert embed.fields[0].name == "Morning Standup"
        assert "9:00–9:30 AM ET" in embed.fields[0].value
        assert "https://calendar.google.com/event?eid=evt1" in embed.fields[0].value

        # Second event
        assert embed.fields[1].name == "Lunch"
        assert "12:00–1:00 PM ET" in embed.fields[1].value
        assert "https://calendar.google.com/event?eid=evt2" in embed.fields[1].value

    def test_duration_formatting(self):
        """format_events_embed uses time range display."""
        events = [
            {
                "summary": "Short",
                "start": {"dateTime": "2026-04-28T14:00:00-04:00"},
                "end": {"dateTime": "2026-04-28T14:15:00-04:00"},
                "htmlLink": "https://calendar.google.com/event?eid=short",
            },
        ]

        embed = format_events_embed(events, "April 28, 2026")

        assert "2:00–2:15 PM ET" in embed.fields[0].value

    def test_missing_htmlLink_falls_back(self):
        """format_events_embed handles events without an htmlLink gracefully."""
        events = [
            {
                "summary": "No Link",
                "start": {"dateTime": "2026-04-28T10:00:00-04:00"},
                "end": {"dateTime": "2026-04-28T11:00:00-04:00"},
            },
        ]

        embed = format_events_embed(events, "April 28, 2026")

        assert embed.fields[0].name == "No Link"
        # Should contain the time range
        assert "10:00–11:00 AM ET" in embed.fields[0].value
        # Should not contain a calendar link since none was provided
        assert "google.com" not in embed.fields[0].value
