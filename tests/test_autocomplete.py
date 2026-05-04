"""Tests for the shared autocomplete module — event_autocomplete and helpers."""

import datetime
import time
from unittest.mock import MagicMock

import pytest

from src.commands.autocomplete import (
    _truncate_for_autocomplete,
    _event_cache,
    event_autocomplete,
)


# ── _truncate_for_autocomplete ──────────────────────────────────────────────


def test_truncate_short_title_unchanged():
    """Short titles are returned unchanged."""
    assert _truncate_for_autocomplete("Team Standup") == "Team Standup"


def test_truncate_exactly_at_limit():
    """Titles exactly at 100 characters are returned unchanged."""
    title = "X" * 100
    result = _truncate_for_autocomplete(title)
    assert result == title
    assert len(result) == 100


def test_truncate_over_limit():
    """Titles over 100 characters are truncated with ellipsis."""
    title = "A" * 120
    result = _truncate_for_autocomplete(title)
    assert len(result) == 100
    assert result.endswith("…")


# ── event_autocomplete ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_calendar_returns_empty():
    """Autocomplete returns empty list when calendar is not configured."""
    interaction = MagicMock()
    interaction.client.calendar = None

    choices = await event_autocomplete(interaction, "test")
    assert choices == []


@pytest.mark.asyncio
async def test_filters_by_substring():
    """Autocomplete returns only events whose summary contains the typed text."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup", "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
        {"id": "evt2", "summary": "Design Review", "start": {"dateTime": "2026-05-03T14:00:00+00:00"}},
        {"id": "evt3", "summary": "Standup Notes", "start": {"dateTime": "2026-05-04T10:00:00+00:00"}},
    ]

    choices = await event_autocomplete(interaction, "standup")

    assert len(choices) == 2
    names = [c.name for c in choices]
    assert any("Team Standup" in n for n in names)
    assert any("Standup Notes" in n for n in names)
    assert not any("Design Review" in n for n in names)


@pytest.mark.asyncio
async def test_empty_query_returns_all():
    """Autocomplete with empty string returns all upcoming events."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup", "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
        {"id": "evt2", "summary": "Design Review", "start": {"dateTime": "2026-05-03T14:00:00+00:00"}},
    ]

    choices = await event_autocomplete(interaction, "")
    assert len(choices) == 2


@pytest.mark.asyncio
async def test_strips_whitespace_and_lowercases_query():
    """Autocomplete normalises the query by stripping whitespace and lowercasing."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup", "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
    ]

    choices = await event_autocomplete(interaction, "  TEAM  ")
    assert len(choices) == 1
    assert "Team Standup" in choices[0].name


@pytest.mark.asyncio
async def test_truncates_long_titles():
    """Autocomplete truncates event summaries longer than 100 characters."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    long_title = "A" * 120
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": long_title, "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
    ]

    choices = await event_autocomplete(interaction, "")
    assert len(choices) == 1
    assert len(choices[0].name) == 100
    assert choices[0].name.endswith("…")


@pytest.mark.asyncio
async def test_labels_include_date_and_time():
    """Choice labels are formatted as 'Month D, H:MM[AM|PM] — Summary'."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {
            "id": "evt1",
            "summary": "BBQ",
            "start": {"dateTime": "2026-05-02T20:00:00+00:00"},
        },
    ]

    choices = await event_autocomplete(interaction, "BBQ")
    assert len(choices) == 1
    # May 2 20:00 UTC = May 2 4:00 PM EDT
    assert choices[0].name == "May 2, 4pm — BBQ"


@pytest.mark.asyncio
async def test_labels_include_minutes_when_not_zero():
    """Choice labels include minutes when they are not :00."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {
            "id": "evt1",
            "summary": "Standup",
            "start": {"dateTime": "2026-05-02T20:30:00+00:00"},
        },
    ]

    choices = await event_autocomplete(interaction, "Standup")
    assert len(choices) == 1
    # May 2 20:30 UTC = May 2 4:30 PM EDT
    assert choices[0].name == "May 2, 4:30pm — Standup"


@pytest.mark.asyncio
async def test_uses_utc_start_of_day_for_time_min():
    """time_min is computed as start of today in UTC, not current time."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = []

    await event_autocomplete(interaction, "")

    # Verify list_events was called with time_min
    call_kwargs = interaction.client.calendar.list_events.call_args.kwargs
    time_min = call_kwargs["time_min"]

    # time_min should be timezone-aware UTC
    assert time_min.tzinfo is not None
    # time_min should be at the start of today in UTC (midnight UTC)
    assert time_min.hour == 0
    assert time_min.minute == 0
    assert time_min.second == 0
    assert time_min.microsecond == 0
    # time_max should be exactly 14 days later
    time_max = call_kwargs["time_max"]
    assert time_max == time_min + datetime.timedelta(days=14)


@pytest.mark.asyncio
async def test_labels_reflect_user_timezone():
    """Choice labels are formatted in the user's configured timezone."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.settings = MagicMock()
    # User has Pacific timezone stored
    interaction.client.settings.get.return_value = "America/Los_Angeles"
    interaction.client.calendar.list_events.return_value = [
        {
            "id": "evt1",
            "summary": "BBQ",
            "start": {"dateTime": "2026-05-02T20:00:00+00:00"},
        },
    ]

    choices = await event_autocomplete(interaction, "BBQ")
    assert len(choices) == 1
    # May 2 20:00 UTC = May 2 1:00 PM PDT (UTC-7 in May)
    assert choices[0].name == "May 2, 1pm — BBQ"


@pytest.mark.asyncio
async def test_cache_hit_skips_api_call():
    """On cache hit within TTL, the API is not called again."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup", "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
    ]

    # First call — populates cache
    await event_autocomplete(interaction, "standup")
    assert interaction.client.calendar.list_events.call_count == 1

    # Second call with same query — should hit cache, no API call
    await event_autocomplete(interaction, "standup")
    assert interaction.client.calendar.list_events.call_count == 1


@pytest.mark.asyncio
async def test_cache_expired_refreshes():
    """When cache expires (30s TTL), a new API call is made."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Team Standup", "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
    ]

    # Populate cache
    await event_autocomplete(interaction, "standup")
    assert interaction.client.calendar.list_events.call_count == 1

    # Age the cache entry by setting its timestamp to 31 seconds ago
    for key in list(_event_cache.keys()):
        events = _event_cache[key][1]
        _event_cache[key] = (time.time() - 31, events)

    # This call should miss the cache and make a new API call
    await event_autocomplete(interaction, "standup")
    assert interaction.client.calendar.list_events.call_count == 2


@pytest.mark.asyncio
async def test_cache_is_keyed_by_calendar_id():
    """Cache entries are separated by calendar_id."""
    _event_cache.clear()

    interaction1 = MagicMock()
    interaction1.client.calendar = MagicMock()
    interaction1.client.calendar._calendar_id = "cal-abc"
    interaction1.client.calendar.list_events.return_value = [
        {"id": "evt1", "summary": "Event A", "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
    ]

    interaction2 = MagicMock()
    interaction2.client.calendar = MagicMock()
    interaction2.client.calendar._calendar_id = "cal-xyz"
    interaction2.client.calendar.list_events.return_value = [
        {"id": "evt2", "summary": "Event B", "start": {"dateTime": "2026-05-02T18:00:00+00:00"}},
    ]

    await event_autocomplete(interaction1, "")
    await event_autocomplete(interaction2, "")

    # Each calendar should have its own API call
    assert interaction1.client.calendar.list_events.call_count == 1
    assert interaction2.client.calendar.list_events.call_count == 1

    # Cache should have two entries
    assert len(_event_cache) == 2


@pytest.mark.asyncio
async def test_api_error_returns_empty():
    """When list_events raises RuntimeError, autocomplete returns empty list."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    interaction.client.calendar.list_events.side_effect = RuntimeError("API error")

    choices = await event_autocomplete(interaction, "test")
    assert choices == []


@pytest.mark.asyncio
async def test_returns_max_25_choices():
    """Autocomplete never returns more than 25 choices (Discord limit)."""
    _event_cache.clear()

    interaction = MagicMock()
    interaction.client.calendar = MagicMock()
    events = [
        {
            "id": f"evt{i}",
            "summary": f"Event {i}",
            "start": {"dateTime": "2026-05-02T18:00:00+00:00"},
        }
        for i in range(30)
    ]
    interaction.client.calendar.list_events.return_value = events

    choices = await event_autocomplete(interaction, "Event")
    assert len(choices) == 25
