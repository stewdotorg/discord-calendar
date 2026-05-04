"""VCR-based integration tests for CalendarService against the real Google Calendar API.

These tests record HTTP interactions to cassettes in tests/cassettes/.
By default, pytest plays back cassettes (no network).  Use ``pytest --record``
to re-record cassettes against the live API.

The tests verify that the CalendarService wrapper correctly interacts with
the Google Calendar API — creating events, listing them, deleting them,
adding attendees, setting reminders, and updating events.

Supports both OAuth2 user credentials (GOOGLE_REFRESH_TOKEN) and
service account (GOOGLE_SERVICE_ACCOUNT_FILE).
"""

import datetime
import hashlib
import os

import pytest

from googleapiclient.errors import HttpError

from src.calendar.auth import load_credentials
from src.calendar.service import CalendarService

# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_calendar_ids() -> tuple[str, str]:
    """Return (key_path, calendar_id) from env, skipping if unset.

    Supports both OAuth2 user credentials (GOOGLE_REFRESH_TOKEN) and
    service account (GOOGLE_SERVICE_ACCOUNT_FILE).  OAuth2 takes
    precedence when both are configured.
    """
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
    key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "")

    if not calendar_id:
        pytest.skip("VCR test requires GOOGLE_CALENDAR_ID environment variable.")

    # OAuth2 is preferred — skip service account validation when it's available
    if refresh_token:
        return key_path, calendar_id

    # Service account fallback — validate the key file exists
    if not key_path:
        pytest.skip(
            "VCR test requires GOOGLE_REFRESH_TOKEN (OAuth2) or "
            "GOOGLE_SERVICE_ACCOUNT_FILE (service account)."
        )

    if not os.path.isfile(key_path):
        pytest.skip(
            f"Service account key file not found: {key_path}. "
            "Set GOOGLE_REFRESH_TOKEN for OAuth2 or provide a valid "
            "service account key."
        )

    return key_path, calendar_id


def _build_service(key_path: str, calendar_id: str) -> CalendarService:
    """Build a CalendarService from the given credentials path and calendar ID."""
    credentials = load_credentials(key_path)
    return CalendarService(credentials, calendar_id)


# Fixed reference date so VCR cassettes remain deterministic across runs.
_REFERENCE_DATE = datetime.datetime(2026, 5, 3, tzinfo=datetime.timezone.utc)


def _make_future_start(days: int, hour: int = 10) -> datetime.datetime:
    """Return a timezone-aware datetime relative to a fixed reference date."""
    dt = _REFERENCE_DATE + datetime.timedelta(days=days)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0)


def _unique_title(suffix: str = "") -> str:
    """Generate a unique, deterministic title for VCR test isolation.

    Uses a seed based on the day so cassettes remain valid for ~24 hours
    before needing re-record for a different value.  An optional *suffix*
    distinguishes titles across different tests within the same day.
    """
    seed = _REFERENCE_DATE.strftime("%Y%m%d") + suffix
    digest = hashlib.md5(seed.encode()).hexdigest()[:8]
    return f"VCR-Test-{digest}"


# ── create_event → list_events → delete_event round-trip ─────────────────────


def test_create_list_delete_roundtrip(vcr):
    """Create an event via the CalendarService, verify it appears in list_events,
    then delete it and confirm it is removed.

    Uses a VCR cassette to record/replay the HTTP interactions.
    """
    key_path, calendar_id = _get_calendar_ids()

    title = _unique_title("roundtrip")
    start = _make_future_start(days=7, hour=10)

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


# ── add_attendees (success) ──────────────────────────────────────────────────


def test_add_attendees_success(vcr):
    """add_attendees successfully adds an attendee via CalendarService.

    Uses the CalendarService.add_attendees() helper which sends
    ``sendUpdates="all"`` to deliver invitation emails.
    Works with both OAuth2 user credentials and service accounts.
    """
    key_path, calendar_id = _get_calendar_ids()

    title = _unique_title("add-attendees")
    start = _make_future_start(days=8, hour=10)

    test_email = "nobody@example.com"

    service = _build_service(key_path, calendar_id)

    # ── Create event ───────────────────────────────────────────────────
    with vcr.use_cassette("test_add_attendees_create"):
        result = service.create_event(
            title=title,
            start=start,
            duration_minutes=30,
            description="VCR add_attendees success test",
        )

    assert result["id"], "Expected a non-empty event ID"
    event_id = result["id"]

    try:
        # ── Add attendee via CalendarService helper ─────────────────────
        with vcr.use_cassette("test_add_attendees_patch"):
            updated_attendees = service.add_attendees(
                event_id=event_id, emails=[test_email]
            )

        emails = [a.get("email") for a in updated_attendees]
        assert test_email in emails, (
            f"Expected {test_email} in attendee list, got {emails}"
        )

        # ── Verify attendee persisted ───────────────────────────────────
        with vcr.use_cassette("test_add_attendees_verify"):
            event = service.get_event(event_id)

        verify_emails = [a.get("email") for a in event.get("attendees", [])]
        assert test_email in verify_emails, (
            f"Expected {test_email} to persist on event, got {verify_emails}"
        )
    finally:
        # ── Clean up: delete the event ──────────────────────────────────
        with vcr.use_cassette("test_add_attendees_cleanup"):
            service.delete_event(event_id)


# ── add_reminders ────────────────────────────────────────────────────────────


def test_add_reminders(vcr):
    """add_reminders sets popup reminders on an event and verifies them."""
    key_path, calendar_id = _get_calendar_ids()

    title = _unique_title("reminders")
    start = _make_future_start(days=9, hour=14)

    service = _build_service(key_path, calendar_id)

    # ── Create event ───────────────────────────────────────────────────
    with vcr.use_cassette("test_add_reminders_create"):
        result = service.create_event(
            title=title,
            start=start,
            duration_minutes=60,
            description="VCR add_reminders test",
        )

    assert result["id"], "Expected a non-empty event ID"
    event_id = result["id"]

    try:
        # ── Set reminders ───────────────────────────────────────────────
        reminder_minutes = [10, 30]
        with vcr.use_cassette("test_add_reminders_patch"):
            reminders = service.add_reminders(
                event_id=event_id, minutes=reminder_minutes
            )

        assert reminders["useDefault"] is False
        overrides = reminders.get("overrides", [])
        override_minutes = sorted(o["minutes"] for o in overrides)
        assert override_minutes == sorted(reminder_minutes), (
            f"Expected reminders {reminder_minutes}, got {override_minutes}"
        )

        # ── Verify reminders persisted ──────────────────────────────────
        with vcr.use_cassette("test_add_reminders_verify"):
            event = service.get_event(event_id)

        saved_reminders = event.get("reminders", {})
        assert saved_reminders.get("useDefault") is False
        saved_overrides = saved_reminders.get("overrides", [])
        saved_minutes = sorted(o["minutes"] for o in saved_overrides)
        assert saved_minutes == sorted(reminder_minutes), (
            f"Expected reminders {reminder_minutes} on event, got {saved_minutes}"
        )
    finally:
        # ── Clean up: delete the event ──────────────────────────────────
        with vcr.use_cassette("test_add_reminders_cleanup"):
            service.delete_event(event_id)


# ── update_event ─────────────────────────────────────────────────────────────


def test_update_event(vcr):
    """update_event patches event fields and verifies the changes."""
    key_path, calendar_id = _get_calendar_ids()

    title = _unique_title("update")
    start = _make_future_start(days=10, hour=11)

    service = _build_service(key_path, calendar_id)

    # ── Create event ───────────────────────────────────────────────────
    with vcr.use_cassette("test_update_event_create"):
        result = service.create_event(
            title=title,
            start=start,
            duration_minutes=45,
            description="Original description for VCR update test",
        )

    assert result["id"], "Expected a non-empty event ID"
    event_id = result["id"]

    try:
        # ── Update event summary and description ────────────────────────
        new_title = title + " (Updated)"
        new_description = "Updated description via VCR integration test"

        with vcr.use_cassette("test_update_event_patch"):
            updated = service.update_event(
                event_id=event_id,
                summary=new_title,
                description=new_description,
            )

        assert updated["id"] == event_id
        assert updated["htmlLink"]

        # ── Verify updates persisted ────────────────────────────────────
        with vcr.use_cassette("test_update_event_verify"):
            event = service.get_event(event_id)

        assert event["summary"] == new_title, (
            f"Expected summary '{new_title}', got '{event['summary']}'"
        )
        assert event["description"] == new_description, (
            f"Expected description '{new_description}', "
            f"got '{event['description']}'"
        )
    finally:
        # ── Clean up: delete the event ──────────────────────────────────
        with vcr.use_cassette("test_update_event_cleanup"):
            service.delete_event(event_id)


# ── delete_event raises HttpError for non-existent event ─────────────────────


def test_delete_nonexistent_event_raises(vcr):
    """delete_event raises HttpError when the event ID does not exist."""
    key_path, calendar_id = _get_calendar_ids()

    service = _build_service(key_path, calendar_id)

    with vcr.use_cassette("test_delete_nonexistent"):
        with pytest.raises(HttpError):
            service.delete_event("nonexistent-event-id-12345")
