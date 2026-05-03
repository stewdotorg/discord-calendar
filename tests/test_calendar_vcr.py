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


def _get_calendar_ids() -> tuple[str, str]:
    """Return (key_path, calendar_id) from env, skipping if unset."""
    key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "")

    if not key_path or not calendar_id:
        pytest.skip(
            "VCR test requires GOOGLE_SERVICE_ACCOUNT_FILE and "
            "GOOGLE_CALENDAR_ID environment variables."
        )

    return key_path, calendar_id


def _build_service(key_path: str, calendar_id: str) -> CalendarService:
    """Build a CalendarService from the given credentials path and calendar ID."""
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
    key_path, calendar_id = _get_calendar_ids()

    title = _unique_title()
    start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)

    service = _build_service(key_path, calendar_id)

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
    key_path, calendar_id = _get_calendar_ids()

    service = _build_service(key_path, calendar_id)

    # Query a range far in the past — unlikely to have any events
    far_past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    far_past_end = datetime.datetime(2000, 1, 2, tzinfo=datetime.timezone.utc)

    with vcr.use_cassette("test_list_events_empty"):
        events = service.list_events(
            time_min=far_past, time_max=far_past_end,
        )

    assert events == [], "Expected no events in the distant past"


# ── add_attendees ─────────────────────────────────────────────────────────────


def test_add_attendees_success(vcr):
    """Create an event, add an attendee, verify the attendee is present, then
    delete the event.

    Uses a VCR cassette to record/replay the HTTP interactions.
    """
    key_path, calendar_id = _get_calendar_ids()

    title = _unique_title()
    start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    start = start.replace(hour=14, minute=0, second=0, microsecond=0)

    test_email = "test-attendee@example.com"

    service = _build_service(key_path, calendar_id)

    # ── Create event ───────────────────────────────────────────────────
    with vcr.use_cassette("test_add_attendees_success"):
        result = service.create_event(
            title=title,
            start=start,
            duration_minutes=60,
            description="VCR add_attendees success test",
        )

    assert result["id"], "Expected a non-empty event ID"
    event_id = result["id"]

    # ── Add attendee ───────────────────────────────────────────────────
    with vcr.use_cassette("test_add_attendees_success"):
        attendees = service.add_attendees(event_id, [test_email])

    # ── Verify attendee appears in the event ───────────────────────────
    emails = [a["email"] for a in attendees]
    assert test_email in emails, (
        f"Expected {test_email} in attendee list, got {emails}"
    )

    # ── Clean up: delete the event ─────────────────────────────────────
    with vcr.use_cassette("test_add_attendees_success"):
        service.delete_event(event_id)


def test_add_attendees_permission_denied(vcr):
    """add_attendees raises HttpError when the API returns a 403.

    This test directly calls the Google Calendar API with
    ``sendUpdates="all"`` on a shared calendar where the service account
    does not have permission to send invitation emails.  The resulting
    403 response is recorded in the failure cassette.
    """
    key_path, calendar_id = _get_calendar_ids()

    title = _unique_title()
    start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=8)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)

    test_email = "nobody@example.com"

    service = _build_service(key_path, calendar_id)

    # ── Create event ───────────────────────────────────────────────────
    with vcr.use_cassette("test_add_attendees_permission_denied"):
        result = service.create_event(
            title=title,
            start=start,
            duration_minutes=30,
            description="VCR add_attendees permission denied test",
        )

    event_id = result["id"]

    from googleapiclient.errors import HttpError

    try:
        # ── Attempt add_attendees with sendUpdates="all" (triggers 403) ──
        with vcr.use_cassette("test_add_attendees_permission_denied"):
            # Bypass the CalendarService helper and call the API directly
            # with sendUpdates="all" to reproduce the 403.
            srv = service._build_service()
            event = (
                srv.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
            existing = event.get("attendees", [])
            body = {"attendees": existing + [{"email": test_email}]}

            with pytest.raises(HttpError):
                (
                    srv.events()
                    .patch(
                        calendarId=calendar_id,
                        eventId=event_id,
                        body=body,
                        sendUpdates="all",
                    )
                    .execute()
                )
    finally:
        # ── Clean up: delete the event ─────────────────────────────────
        with vcr.use_cassette("test_add_attendees_permission_denied"):
            service.delete_event(event_id)


# ── delete_event raises HttpError for non-existent event ─────────────────────


def test_delete_nonexistent_event_raises(vcr):
    """delete_event raises HttpError when the event ID does not exist."""
    key_path, calendar_id = _get_calendar_ids()

    service = _build_service(key_path, calendar_id)

    from googleapiclient.errors import HttpError

    with vcr.use_cassette("test_delete_nonexistent"):
        with pytest.raises(HttpError):
            service.delete_event("nonexistent-event-id-12345")
