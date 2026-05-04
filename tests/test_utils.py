"""Tests for utility functions — embed formatting, timezone conversion,
and when-param parsing."""

import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.utils import (
    _format_time_range_eastern,
    format_events_embed,
    get_today_eastern_range,
    parse_date_eastern,
    parse_when,
    resolve_mentions,
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


# ═══════════════════════════════════════════════════════════════════════════════
#  NLP Date Parsing (dateparser) — Issue #7
# ═══════════════════════════════════════════════════════════════════════════════

# Fixed reference point for relative date parsing tests.
# May 1, 2026 12:00 PM US Eastern (EDT, UTC-4).
_BASE = datetime.datetime(2026, 5, 1, 12, 0)


class TestParseWhenDateparser:
    """Tests for parse_when using dateparser NLP parsing (Issue #7)."""

    # ── Valid inputs ────────────────────────────────────────────────────────

    def test_dateparser_tuesday_at_3pm(self):
        """Parses day-of-week with time and AM/PM suffix."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tuesday 3pm")
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 5
        assert result.hour == 19  # 3pm EDT → 7pm UTC
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_dateparser_may_15_2026_230pm(self):
        """Parses month-name date with year and minutes+AM/PM."""
        result = parse_when("May 15 2026 2:30pm")
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 15
        assert result.hour == 18  # 2:30pm EDT → 6:30pm UTC
        assert result.minute == 30
        assert result.tzinfo == datetime.timezone.utc

    def test_dateparser_in_2_hours(self):
        """Parses relative 'in N hours' from the current time."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("in 2 hours")
        # _BASE=May 1 12:00 UTC = 8:00 EDT; +2h = 10:00 EDT = 14:00 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 14
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_dateparser_tomorrow_morning(self):
        """Parses 'tomorrow' with time-of-day word expanded to a clock time."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow morning")
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 2
        assert result.hour == 13  # 9am EDT → 1pm UTC
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_dateparser_friday_at_noon(self):
        """Parses day-of-week with 'at noon'."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("friday at noon")
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 8
        assert result.hour == 16  # 12pm EDT → 4pm UTC
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_dateparser_slash_date_24h(self):
        """Parses US slash date with year and 24-hour time."""
        result = parse_when("5/15/2026 14:00")
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 15
        assert result.hour == 18  # 2pm EDT → 6pm UTC
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_dateparser_june_5th_4pm(self):
        """Parses month-name date with ordinal suffix and AM/PM."""
        result = parse_when("June 5th 4pm")
        assert result.year == 2026
        assert result.month == 6
        assert result.day == 5
        assert result.hour == 20  # 4pm EDT → 8pm UTC
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    # ── Invalid inputs ──────────────────────────────────────────────────────

    @pytest.mark.parametrize("garbage", ["asdfasdf", "blarb", "not a date"])
    def test_dateparser_garbage_raises_value_error(self, garbage):
        """Garbage input that neither dateparser nor manual parser can handle."""
        with pytest.raises(ValueError):
            parse_when(garbage)

    def test_dateparser_empty_string(self):
        """Empty string is rejected before any parsing is attempted."""
        with pytest.raises(ValueError):
            parse_when("")

    # ── Ambiguous input ─────────────────────────────────────────────────────

    def test_dateparser_ambiguous_us_month_first(self):
        """Ambiguous date defaults to US month-first interpretation."""
        result = parse_when("05/06/2026")
        assert result.month == 5
        assert result.day == 6
        assert result.year == 2026
        assert result.tzinfo == datetime.timezone.utc

    # ── Relative time: 'in X hours/minutes' ───────────────────────────────

    def test_relative_today_in_hours(self):
        """Parses 'today in N hours' as relative time from RELATIVE_BASE."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("today in 5 hours")
        # _BASE=May 1 12:00 UTC = 8:00 EDT; +5h = 13:00 EDT = 17:00 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 17
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_relative_tomorrow_in_hour(self):
        """Parses 'tomorrow in 1 hour' as relative time from RELATIVE_BASE."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow in 1 hour")
        # _BASE=May 1 12:00 UTC = 8:00 EDT; +1 day +1h = May 2 9:00 EDT = 13:00 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 2
        assert result.hour == 13
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_relative_next_monday_3am(self):
        """Parses 'monday 3:00' as next Monday 3am Eastern."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("monday 3:00")
        # May 1 is Friday, next Monday = May 4
        # Monday 3:00 AM EDT = 7:00 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 4
        assert result.hour == 7
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_relative_in_minutes(self):
        """Parses standalone 'in 30 minutes' from the current time."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("in 30 minutes")
        # _BASE=May 1 12:00 UTC = 8:00 EDT; +30m = 8:30 EDT = 12:30 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 30
        assert result.tzinfo == datetime.timezone.utc

    def test_relative_short_form_h(self):
        """Parses 'in 1h' as 1 hour from now (via dateparser)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("in 1h")
        # _BASE=May 1 12:00 UTC = 8:00 EDT; +1h = 9:00 EDT = 13:00 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 13
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_relative_short_form_hr(self):
        """Parses 'in 1hr' as 1 hour from now (via dateparser)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("in 1hr")
        # _BASE=May 1 12:00 UTC = 8:00 EDT; +1h = 9:00 EDT = 13:00 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 13
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_relative_stacked_minutes(self):
        """Parses 'in 5 min' as 5 minutes from now (via dateparser)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("in 5 min")
        # _BASE=May 1 12:00 UTC = 8:00 EDT; +5m = 8:05 EDT = 12:05 UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 5
        assert result.tzinfo == datetime.timezone.utc

    # ── Timezone parameter ────────────────────────────────────────────────

    def test_custom_timezone_pacific(self):
        """parse_when accepts a timezone parameter and interprets input in that zone."""
        pacific = ZoneInfo("America/Los_Angeles")
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("May 1 3pm", tz=pacific)
        # 3pm PDT (UTC-7 in May) = 10pm UTC
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 1
        assert result.hour == 22
        assert result.minute == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_default_timezone_is_eastern(self):
        """parse_when defaults to US Eastern when no timezone is provided."""
        result = parse_when("May 1 3pm")
        # 3pm EDT (UTC-4 in May) = 7pm UTC
        assert result.hour == 19
        assert result.tzinfo == datetime.timezone.utc


# ═══════════════════════════════════════════════════════════════════════════════
#  parse_date_eastern — Issue #10
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseDateEastern:
    """Tests for parse_date_eastern (YYYY-MM-DD in Eastern → UTC)."""

    def test_valid_date_returns_utc_datetime(self):
        """parse_date_eastern parses YYYY-MM-DD as Eastern midnight
        and returns a timezone-aware UTC datetime."""
        result = parse_date_eastern("2026-05-15")
        assert result.tzinfo == datetime.timezone.utc
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 15
        # May in EDT (UTC-4), midnight Eastern = 4:00 UTC
        assert result.hour == 4
        assert result.minute == 0

    def test_valid_date_is_start_of_day_in_eastern(self):
        """parse_date_eastern returns midnight Eastern for the given date."""
        result = parse_date_eastern("2026-01-15")
        assert result.tzinfo == datetime.timezone.utc
        # January in EST (UTC-5), midnight Eastern = 5:00 UTC
        assert result.hour == 5
        assert result.minute == 0

    @pytest.mark.parametrize("invalid", ["not-a-date", "", "05/15/2026", "2026-13-01"])
    def test_invalid_date_raises_value_error(self, invalid):
        """parse_date_eastern raises ValueError for invalid date strings."""
        with pytest.raises(ValueError):
            parse_date_eastern(invalid)


# ═══════════════════════════════════════════════════════════════════════════════
#  resolve_mentions — Issue #22
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveMentions:
    """Tests for resolve_mentions."""

    def test_extracts_discord_id_and_resolves_email(self):
        """resolve_mentions extracts Discord ID from <@id> and looks up stored email."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.get.return_value = "bob@example.com"

        resolved, warnings = resolve_mentions(["<@123456789>"], settings)

        settings.get.assert_called_once_with("123456789", "email")
        assert resolved == ["bob@example.com"]
        assert warnings == []

    def test_passes_raw_emails_through(self):
        """resolve_mentions passes raw email addresses through unchanged."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.get.return_value = None

        resolved, warnings = resolve_mentions(
            ["alice@example.com"], settings
        )

        assert resolved == ["alice@example.com"]
        assert warnings == []

    def test_warns_when_mention_has_no_stored_email(self):
        """resolve_mentions returns a warning when a mentioned user has no stored email."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.get.return_value = None

        resolved, warnings = resolve_mentions(["<@999999>"], settings)

        assert resolved == []
        assert len(warnings) == 1
        assert "no email stored" in warnings[0].lower()
        assert "<@999999>" in warnings[0]

    def test_resolves_mixed_mentions_and_emails(self):
        """resolve_mentions handles a mix of @mentions and raw emails."""
        from unittest.mock import MagicMock

        def mock_get(discord_id, key):
            if discord_id == "111111":
                return "bob@example.com"
            if discord_id == "222222":
                return "carol@example.com"
            return None

        settings = MagicMock()
        settings.get = mock_get

        resolved, warnings = resolve_mentions(
            ["<@111111>", "alice@example.com", "<@222222>"],
            settings,
        )

        assert resolved == [
            "bob@example.com",
            "alice@example.com",
            "carol@example.com",
        ]
        assert warnings == []

    def test_mixed_resolved_and_unresolved_mentions(self):
        """resolve_mentions resolves what it can and warns about the rest."""
        from unittest.mock import MagicMock

        def mock_get(discord_id, key):
            if discord_id == "111111":
                return "bob@example.com"
            return None

        settings = MagicMock()
        settings.get = mock_get

        resolved, warnings = resolve_mentions(
            ["<@111111>", "<@999999>", "alice@example.com"],
            settings,
        )

        assert resolved == ["bob@example.com", "alice@example.com"]
        assert len(warnings) == 1
        assert "<@999999>" in warnings[0]

    def test_handles_whitespace_around_items(self):
        """resolve_mentions strips whitespace around each item."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.get.return_value = "bob@example.com"

        resolved, warnings = resolve_mentions(
            ["  <@123456789>  ", "  alice@example.com  "],
            settings,
        )

        assert resolved == ["bob@example.com", "alice@example.com"]
        assert warnings == []

    def test_handles_nickname_mention_format(self):
        """resolve_mentions handles <@!id> (nickname) mention format."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.get.return_value = "bob@example.com"

        resolved, warnings = resolve_mentions(["<@!123456789>"], settings)

        settings.get.assert_called_once_with("123456789", "email")
        assert resolved == ["bob@example.com"]
        assert warnings == []

    def test_empty_list_returns_empty(self):
        """resolve_mentions returns empty results for an empty list."""
        from unittest.mock import MagicMock

        settings = MagicMock()

        resolved, warnings = resolve_mentions([], settings)

        assert resolved == []
        assert warnings == []
