"""Tests for utility functions — embed formatting and timezone conversion."""

import datetime

from src.utils import format_events_embed, get_today_eastern_range


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

        # First event
        assert embed.fields[0].name == "Morning Standup"
        assert "9:00 AM" in embed.fields[0].value
        assert "30m" in embed.fields[0].value
        assert "https://calendar.google.com/event?eid=evt1" in embed.fields[0].value

        # Second event
        assert embed.fields[1].name == "Lunch"
        assert "12:00 PM" in embed.fields[1].value
        assert "1h" in embed.fields[1].value
        assert "https://calendar.google.com/event?eid=evt2" in embed.fields[1].value

    def test_duration_formatting(self):
        """format_events_embed formats durations correctly for minutes and hours."""
        events = [
            {
                "summary": "Short",
                "start": {"dateTime": "2026-04-28T14:00:00-04:00"},
                "end": {"dateTime": "2026-04-28T14:15:00-04:00"},
                "htmlLink": "https://calendar.google.com/event?eid=short",
            },
        ]

        embed = format_events_embed(events, "April 28, 2026")

        assert "15m" in embed.fields[0].value
        assert "2:00 PM" in embed.fields[0].value

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
        # Should not contain a calendar link since none was provided
        assert "google.com" not in embed.fields[0].value
