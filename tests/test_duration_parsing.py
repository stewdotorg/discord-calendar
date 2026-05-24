"""Tests for duration/time-range parsing with AM/PM inference (Issue #36).

All tests pin ``_dateparser_now`` to a fixed reference point so relative
expressions like "tomorrow" and "friday" are deterministic.

Reference: 2026-05-01 12:00 UTC (Friday, 8:00 AM EDT, UTC-4).
"""

import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from src.utils import parse_when

# Fixed reference point for relative date parsing tests.
# Friday, May 1, 2026 12:00 UTC = 8:00 AM EDT (UTC-4).
_BASE = datetime.datetime(2026, 5, 1, 12, 0, tzinfo=datetime.timezone.utc)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _utc(y, m, d, h, mi=0):
    """Shorthand for building a timezone-aware UTC datetime."""
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
#  Duration patterns — dash separator
# ═══════════════════════════════════════════════════════════════════════════════


class TestDurationDash:
    """Duration patterns using '-' as the time-range separator."""

    def test_tomorrow_9_11(self):
        """tomorrow 9-11 → 9:00 AM to 11:00 AM."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 9-11")
        # May 2 9am EDT = 13:00 UTC, May 2 11am EDT = 15:00 UTC
        assert start == _utc(2026, 5, 2, 13)
        assert end == _utc(2026, 5, 2, 15)

    def test_tomorrow_4_6pm(self):
        """tomorrow 4-6pm → start inherits pm from explicit end."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 4-6pm")
        # May 2 4pm EDT = 20:00 UTC, May 2 6pm EDT = 22:00 UTC
        assert start == _utc(2026, 5, 2, 20)
        assert end == _utc(2026, 5, 2, 22)

    def test_friday_1030_1145(self):
        """friday 10:30-11:45 → both inferred AM."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("friday 10:30-11:45")
        # Next Friday from May 1 = May 8. 10:30am EDT = 14:30 UTC, 11:45am EDT = 15:45 UTC
        assert start == _utc(2026, 5, 8, 14, 30)
        assert end == _utc(2026, 5, 8, 15, 45)

    def test_may_1_9am_5pm(self):
        """may 1 9am-5pm → both explicit."""
        # Use a RELATIVE_BASE of midnight EDT so dateparser's
        # PREFER_DATES_FROM:future doesn't skip past AM times on May 1.
        _midnight_base = datetime.datetime(2026, 5, 1, 4, 0, tzinfo=datetime.timezone.utc)
        with patch("src.utils._dateparser_now", return_value=_midnight_base):
            start, end = parse_when("may 1 9am-5pm")
        # May 1 9am EDT = 13:00 UTC, 5pm EDT = 21:00 UTC
        assert start == _utc(2026, 5, 1, 13)
        assert end == _utc(2026, 5, 1, 21)

    def test_tomorrow_12_2(self):
        """tomorrow 12-2 → 12→PM, 2→PM (independent inference)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 12-2")
        # May 2 12pm EDT = 16:00 UTC, 2pm EDT = 18:00 UTC
        assert start == _utc(2026, 5, 2, 16)
        assert end == _utc(2026, 5, 2, 18)

    def test_tomorrow_8_10(self):
        """tomorrow 8-10 → 8→PM, 10→PM (independent inference)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 8-10")
        # May 2 8pm EDT = 0:00 UTC May 3, 10pm EDT = 2:00 UTC May 3
        assert start == _utc(2026, 5, 3, 0)
        assert end == _utc(2026, 5, 3, 2)

    def test_tomorrow_5_7(self):
        """tomorrow 5-7 → 5→PM, 7→PM (independent inference)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 5-7")
        # May 2 5pm EDT = 21:00 UTC, 7pm EDT = 23:00 UTC
        assert start == _utc(2026, 5, 2, 21)
        assert end == _utc(2026, 5, 2, 23)

    def test_tomorrow_1_3pm(self):
        """tomorrow 1-3pm → start inherits pm from explicit end."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 1-3pm")
        # May 2 1pm EDT = 17:00 UTC, 3pm EDT = 19:00 UTC
        assert start == _utc(2026, 5, 2, 17)
        assert end == _utc(2026, 5, 2, 19)

    def test_tomorrow_4pm_6(self):
        """tomorrow 4pm-6 → end inherits pm from explicit start."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 4pm-6")
        # May 2 4pm EDT = 20:00 UTC, 6pm EDT = 22:00 UTC
        assert start == _utc(2026, 5, 2, 20)
        assert end == _utc(2026, 5, 2, 22)

    def test_friday_11_1(self):
        """friday 11-1 → 11→AM, 1→PM (independent inference, crossing noon)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("friday 11-1")
        # Next Friday = May 8. 11am EDT = 15:00 UTC, 1pm EDT = 17:00 UTC
        assert start == _utc(2026, 5, 8, 15)
        assert end == _utc(2026, 5, 8, 17)

    def test_tomorrow_930_1045am(self):
        """tomorrow 9:30-10:45am → start inherits am from explicit end."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 9:30-10:45am")
        # May 2 9:30am EDT = 13:30 UTC, 10:45am EDT = 14:45 UTC
        assert start == _utc(2026, 5, 2, 13, 30)
        assert end == _utc(2026, 5, 2, 14, 45)

    def test_tomorrow_1230_2(self):
        """tomorrow 12:30-2 → 12→PM, 2→PM (independent inference)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 12:30-2")
        # May 2 12:30pm EDT = 16:30 UTC, 2pm EDT = 18:00 UTC
        assert start == _utc(2026, 5, 2, 16, 30)
        assert end == _utc(2026, 5, 2, 18)

    # ── Dash without spaces ─────────────────────────────────────────────────

    def test_dash_no_spaces(self):
        """Dash separator works without spaces: '9-11'."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 9-11")
        assert start == _utc(2026, 5, 2, 13)
        assert end == _utc(2026, 5, 2, 15)

    def test_dash_spaces_around(self):
        """Dash separator works with spaces: '9 - 11'."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 9 - 11")
        assert start == _utc(2026, 5, 2, 13)
        assert end == _utc(2026, 5, 2, 15)


# ═══════════════════════════════════════════════════════════════════════════════
#  Duration patterns — "to" word separator
# ═══════════════════════════════════════════════════════════════════════════════


class TestDurationTo:
    """Duration patterns using 'to' as the time-range separator."""

    def test_tomorrow_4_to_6pm(self):
        """tomorrow 4 to 6pm → start inherits pm from explicit end."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 4 to 6pm")
        # May 2 4pm EDT = 20:00 UTC, 6pm EDT = 22:00 UTC
        assert start == _utc(2026, 5, 2, 20)
        assert end == _utc(2026, 5, 2, 22)

    def test_friday_2pm_to_4pm(self):
        """friday 2pm to 4pm → both explicit pm."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("friday 2pm to 4pm")
        # Next Friday = May 8. 2pm EDT = 18:00 UTC, 4pm EDT = 20:00 UTC
        assert start == _utc(2026, 5, 8, 18)
        assert end == _utc(2026, 5, 8, 20)

    def test_tomorrow_10_to_11(self):
        """tomorrow 10 to 11 → both inferred AM."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 10 to 11")
        # May 2 10am EDT = 14:00 UTC, 11am EDT = 15:00 UTC
        assert start == _utc(2026, 5, 2, 14)
        assert end == _utc(2026, 5, 2, 15)

    def test_tomorrow_9_to_11am(self):
        """tomorrow 9 to 11am → start inherits am from explicit end."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 9 to 11am")
        # May 2 9am EDT = 13:00 UTC, 11am EDT = 15:00 UTC
        assert start == _utc(2026, 5, 2, 13)
        assert end == _utc(2026, 5, 2, 15)

    def test_to_case_insensitive(self):
        """'to' separator is case-insensitive: '4 TO 6pm'."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 4 TO 6pm")
        assert start == _utc(2026, 5, 2, 20)
        assert end == _utc(2026, 5, 2, 22)

    def test_to_word_boundary(self):
        """'to' only matches as a word boundary, not inside words."""
        # "tomato 4pm" is not a range — "to" is inside "tomato"
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 4pm")
        # Should be a single datetime, not a tuple
        assert isinstance(result, datetime.datetime)
        assert result == _utc(2026, 5, 2, 20)


# ═══════════════════════════════════════════════════════════════════════════════
#  Non-range inputs — AM/PM inference for ambiguous times
# ═══════════════════════════════════════════════════════════════════════════════


class TestNonRangeInference:
    """AM/PM inference for non-range (single time) inputs."""

    def test_tomorrow_10_infers_am(self):
        """tomorrow 10 → 10am (hour 10 → AM)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 10")
        assert isinstance(result, datetime.datetime)
        assert result == _utc(2026, 5, 2, 14)  # 10am EDT = 14:00 UTC

    def test_tomorrow_3_infers_pm(self):
        """tomorrow 3 → 3pm (hour 3 → PM)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 3")
        assert isinstance(result, datetime.datetime)
        assert result == _utc(2026, 5, 2, 19)  # 3pm EDT = 19:00 UTC

    def test_tomorrow_9_infers_am(self):
        """tomorrow 9 → 9am (hour 9 → AM)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 9")
        assert result == _utc(2026, 5, 2, 13)  # 9am EDT = 13:00 UTC

    def test_tomorrow_12_infers_pm(self):
        """tomorrow 12 → 12pm (hour 12 → PM)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 12")
        assert result == _utc(2026, 5, 2, 16)  # 12pm EDT = 16:00 UTC

    def test_tomorrow_8_infers_pm(self):
        """tomorrow 8 → 8pm (hour 8 → PM)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 8")
        assert result == _utc(2026, 5, 3, 0)  # 8pm EDT = 00:00 UTC next day

    def test_tomorrow_9am_explicit_preserved(self):
        """tomorrow 9am → explicit am preserved."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 9am")
        assert result == _utc(2026, 5, 2, 13)

    def test_tomorrow_4pm_explicit_preserved(self):
        """tomorrow 4pm → explicit pm preserved."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 4pm")
        assert result == _utc(2026, 5, 2, 20)


# ═══════════════════════════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestDurationEdgeCases:
    """Edge cases for duration parsing."""

    def test_dash_in_iso_date_not_confused(self):
        """Dash in ISO date (2026-05-01) is NOT interpreted as a time range."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("2026-05-01 14:00")
        # Single datetime, not a tuple
        assert isinstance(result, datetime.datetime)
        # 2pm EDT = 18:00 UTC
        assert result == _utc(2026, 5, 1, 18)

    def test_quoted_when_string(self):
        """Quoted when strings are handled (strip quotes)."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when('"tomorrow 9-11"')
        assert start == _utc(2026, 5, 2, 13)
        assert end == _utc(2026, 5, 2, 15)

    def test_raises_value_error_for_empty(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_when("")

    def test_raises_value_error_for_garbage(self):
        """Garbage input raises ValueError."""
        with pytest.raises(ValueError):
            parse_when("asdfasdf")

    def test_duration_with_explicit_both_sides(self):
        """When both sides have explicit AM/PM, use them as-is."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 9am-5pm")
        assert start == _utc(2026, 5, 2, 13)  # 9am
        assert end == _utc(2026, 5, 2, 21)    # 5pm


# ═══════════════════════════════════════════════════════════════════════════════
#  Timezone parameter
# ═══════════════════════════════════════════════════════════════════════════════


class TestDurationTimezone:
    """Duration parsing with custom timezone."""

    def test_duration_with_pacific_timezone(self):
        """Duration parsing respects the timezone parameter."""
        pacific = ZoneInfo("America/Los_Angeles")
        with patch("src.utils._dateparser_now", return_value=_BASE):
            start, end = parse_when("tomorrow 9-11", tz=pacific)
        # May 2 9am PDT (UTC-7) = 16:00 UTC, 11am PDT = 18:00 UTC
        assert start == _utc(2026, 5, 2, 16)
        assert end == _utc(2026, 5, 2, 18)

    def test_non_range_with_pacific_timezone(self):
        """Non-range parsing with AM/PM inference respects timezone."""
        pacific = ZoneInfo("America/Los_Angeles")
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow 10", tz=pacific)
        # May 2 10am PDT (UTC-7) = 17:00 UTC
        assert result == _utc(2026, 5, 2, 17)


# ═══════════════════════════════════════════════════════════════════════════════
#  Legacy non-range inputs — ensure no regression
# ═══════════════════════════════════════════════════════════════════════════════


class TestLegacyNonRange:
    """Existing non-range parse_when inputs still work correctly."""

    def test_dateparser_tuesday_at_3pm(self):
        """Parses day-of-week with time and AM/PM suffix."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tuesday 3pm")
        assert isinstance(result, datetime.datetime)
        assert result == _utc(2026, 5, 5, 19)  # Tuesday May 5 3pm EDT = 19:00 UTC

    def test_dateparser_in_2_hours(self):
        """Parses relative 'in N hours' from the current time."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("in 2 hours")
        assert isinstance(result, datetime.datetime)
        # 8am EDT + 2h = 10am EDT = 14:00 UTC
        assert result == _utc(2026, 5, 1, 14)

    def test_dateparser_tomorrow_morning(self):
        """Parses 'tomorrow' with time-of-day word."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("tomorrow morning")
        assert isinstance(result, datetime.datetime)
        # May 2 9am EDT = 13:00 UTC
        assert result == _utc(2026, 5, 2, 13)

    def test_dateparser_may_15_2026_230pm(self):
        """Parses month-name date with year and minutes+AM/PM."""
        result = parse_when("May 15 2026 2:30pm")
        assert isinstance(result, datetime.datetime)
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 15
        assert result.hour == 18
        assert result.minute == 30

    def test_dateparser_in_30_minutes(self):
        """Parses standalone 'in 30 minutes'."""
        with patch("src.utils._dateparser_now", return_value=_BASE):
            result = parse_when("in 30 minutes")
        assert isinstance(result, datetime.datetime)
        # 8am EDT + 30m = 8:30am EDT = 12:30 UTC
        assert result == _utc(2026, 5, 1, 12, 30)
