"""VCR-based integration tests for CalendarService against the real Google Calendar API.

These tests record HTTP interactions to cassettes in tests/cassettes/.
By default, pytest plays back cassettes (no network).  Use `pytest --record`
to re-record cassettes against the live API.

The tests verify that the CalendarService wrapper correctly interacts with
the Google Calendar API — creating events, listing them, and deleting them.
"""

import datetime
import os
import uuid

import pytest

from src.calendar.auth import load_credentials
from src.calendar.service import CalendarService

# ── Helpers ──────────────────────────────────────────────────────────────────


def _requires_calendar_config():
    """Check that the required env vars are set."""
    key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "")

    if not key_path or not calendar_id:
        pytest.skip(
            "VCR test requires GOOGLE_SERVICE_ACCOUNT_FILE and "
            "GOOGLE_CALENDAR_ID environment variables."
        )


def _build_service():
    """Build a CalendarService from environment variables."""
    key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "")

    credentials = load_credentials(key_path)
    return CalendarService(credentials, calendar_id)


def _unique_title() -> str:
    """Generate a unique event title for test isolation."""
    return f"VCR-Test-{uuid.uuid4().hex[:8]}"


# ── create_event → list_events → delete_event round-trip ─────────────────────


def test_create_list_delete_roundtrip(vcr):
    """Create an event via the CalendarService, verify it appears in list_events,
    then delete it and confirm it is removed.

    Uses a VCR cassette to record/replay the HTTP interactions.
    """
    _requires_calendar_config()

    title = _unique_title()
    start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)

    service = _build_service()

    # ── Create ──────────────────────────────────────────────────────────
    with vcr.use_cassette("test_create_event"):
        result = service.create_event(
            title=title,
            start=start,
            duration_minutes=30,
            description="VCR integration test event",
        )

    assert result["id"], "Expected a non-empty event ID"
    assert result["htmlLink"], "Expected a non-empty htmlLink"
    event_id = result["id"]

    # ── List ────────────────────────────────────────────────────────────
    time_min = start - datetime.timedelta(hours=1)
    time_max = start + datetime.timedelta(hours=2)

    with vcr.use_cassette("test_list_created_event"):
        events = service.list_events(time_min=time_min, time_max=time_max)

    matching = [e for e in events if e.get("id") == event_id]
    assert len(matching) == 1, (
        f"Expected exactly one event with id {event_id}, got {len(matching)}"
    )
    assert matching[0]["summary"] == title

    # ── Delete ──────────────────────────────────────────────────────────
    with vcr.use_cassette("test_delete_event"):
        delete_result = service.delete_event(event_id)

    assert delete_result["summary"] == title
    assert delete_result["start"]

    # ── Verify deletion ─────────────────────────────────────────────────
    with vcr.use_cassette("test_verify_deleted"):
        events_after = service.list_events(
            time_min=time_min, time_max=time_max,
        )

    remaining_ids = [e["id"] for e in events_after]
    assert event_id not in remaining_ids, (
        f"Event {event_id} should not appear after deletion"
    )


# ── list_events returns empty when no events in range ────────────────────────


def test_list_events_empty_range(vcr):
    """list_events returns an empty list when querying a range with no events."""
    _requires_calendar_config()

    service = _build_service()

    # Query a range far in the past — unlikely to have any events
    far_past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    far_past_end = datetime.datetime(2000, 1, 2, tzinfo=datetime.timezone.utc)

    with vcr.use_cassette("test_list_events_empty"):
        events = service.list_events(
            time_min=far_past, time_max=far_past_end,
        )

    assert events == [], "Expected no events in the distant past"


# ── delete_event raises HttpError for non-existent event ─────────────────────


def test_delete_nonexistent_event_raises(vcr):
    """delete_event raises HttpError when the event ID does not exist."""
    _requires_calendar_config()

    service = _build_service()

    from googleapiclient.errors import HttpError

    with vcr.use_cassette("test_delete_nonexistent"):
        with pytest.raises(HttpError):
            service.delete_event("nonexistent-event-id-12345")
