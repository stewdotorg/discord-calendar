"""Google Calendar service — thin wrapper around the Calendar API."""

import datetime
import logging

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class CalendarService:
    """Thin wrapper over the Google Calendar API.

    Delegates auth to a service account and targets a single
    shared calendar identified by its calendar ID.
    """

    def __init__(self, credentials: Credentials, calendar_id: str) -> None:
        self._credentials = credentials
        self._calendar_id = calendar_id

    def _build_service(self):
        """Build and return a Calendar API resource object."""
        return build("calendar", "v3", credentials=self._credentials)

    def verify_access(self) -> str:
        """Verify the service account can access the target calendar.

        Calls calendarList.get to retrieve calendar metadata.

        Returns:
            The calendar summary (human-readable name).

        Raises:
            RuntimeError: If the API call fails for any reason (auth, not found, etc.)
        """
        service = self._build_service()
        try:
            result = (
                service.calendars()
                .get(calendarId=self._calendar_id)
                .execute()
            )
        except HttpError as exc:
            msg = f"Failed to access calendar ({self._calendar_id}): {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc

        summary = result.get("summary", "Unnamed Calendar")
        logger.info("Calendar connected: %s", summary)
        return summary

    def create_event(
        self,
        title: str,
        start: datetime.datetime,
        duration_minutes: int = 60,
        description: str | None = None,
        creator_discord_id: str | None = None,
    ) -> dict:
        """Create a Google Calendar event.

        Args:
            title: Event title (summary).
            start: Event start time as a timezone-aware datetime.
            duration_minutes: Duration in minutes (default 60).
            description: Optional event description.
            creator_discord_id: Optional Discord user ID stored in
                extendedProperties.private.createdBy.

        Returns:
            A dict with 'id' (Google Calendar event ID) and 'htmlLink'.

        Raises:
            HttpError: If the Calendar API call fails.
        """
        end = start + datetime.timedelta(minutes=duration_minutes)

        body = {
            "summary": title,
            "start": {
                "dateTime": start.isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end.isoformat(),
                "timeZone": "UTC",
            },
        }

        if description is not None:
            body["description"] = description

        if creator_discord_id is not None:
            body["extendedProperties"] = {
                "private": {"createdBy": creator_discord_id}
            }

        service = self._build_service()
        result = (
            service.events()
            .insert(calendarId=self._calendar_id, body=body)
            .execute()
        )

        return {"id": result["id"], "htmlLink": result["htmlLink"]}

    def list_events(
        self,
        time_min: datetime.datetime,
        time_max: datetime.datetime,
        q: str | None = None,
        max_results: int = 250,
    ) -> list[dict]:
        """List events in a time range.

        Args:
            time_min: Start of the time range (timezone-aware datetime).
            time_max: End of the time range (timezone-aware datetime).
            q: Optional search keyword to filter events by title/description.
            max_results: Maximum number of events to return.

        Returns:
            List of event dicts as returned by the Google Calendar API,
            ordered by start time.

        Raises:
            RuntimeError: If the API call fails.
        """
        service = self._build_service()
        params = {
            "calendarId": self._calendar_id,
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if q is not None:
            params["q"] = q
        try:
            result = (
                service.events()
                .list(**params)
                .execute()
            )
        except HttpError as exc:
            msg = f"Failed to list events ({self._calendar_id}): {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc

        return result.get("items", [])

    def add_attendees(self, event_id: str, emails: list[str]) -> list[dict]:
        """Add attendees to an existing event.

        Reads the current event to get any existing attendees, appends the
        new email addresses, and patches the event. Google Calendar sends
        invitation emails automatically.

        Args:
            event_id: The Google Calendar event ID.
            emails: List of email addresses to add as attendees.

        Returns:
            The updated attendee list from the API response.

        Raises:
            HttpError: If the Calendar API call fails.
        """
        service = self._build_service()

        event = (
            service.events()
            .get(calendarId=self._calendar_id, eventId=event_id)
            .execute()
        )

        existing = event.get("attendees", [])
        new_attendees = [{"email": email} for email in emails]
        body = {"attendees": existing + new_attendees}

        result = (
            service.events()
            .patch(
                calendarId=self._calendar_id,
                eventId=event_id,
                body=body,
            )
            .execute()
        )

        return result.get("attendees", [])

    def add_reminders(self, event_id: str, minutes: list[int]) -> dict:
        """Set reminders on an event.

        Replaces any existing reminders with the provided list of minutes.
        Each value in ``minutes`` creates a popup reminder that many minutes
        before the event start.

        Args:
            event_id: The Google Calendar event ID.
            minutes: List of integers representing minutes before the event
                start (e.g. ``[10, 30]`` for 10min and 30min reminders).

        Returns:
            The updated reminders config dict with ``useDefault`` and
            ``overrides`` keys.

        Raises:
            HttpError: If the Calendar API call fails.
        """
        service = self._build_service()

        body = {
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": m} for m in minutes
                ],
            }
        }

        result = (
            service.events()
            .patch(
                calendarId=self._calendar_id,
                eventId=event_id,
                body=body,
            )
            .execute()
        )

        return result.get("reminders", {})

    def delete_event(self, event_id: str) -> dict:
        """Delete a Google Calendar event.

        Fetches event metadata before deleting so the caller can
        confirm the deletion with event title and date.

        Deleting an event from Google Calendar automatically sends
        cancellation emails to any attendees.

        Args:
            event_id: The Google Calendar event ID to delete.

        Returns:
            A dict with 'summary' and 'start' (dateTime string) for
            use in the confirmation message.

        Raises:
            HttpError: If the Calendar API call fails.
        """
        service = self._build_service()

        event = (
            service.events()
            .get(calendarId=self._calendar_id, eventId=event_id)
            .execute()
        )

        service.events().delete(
            calendarId=self._calendar_id, eventId=event_id
        ).execute()

        return {
            "summary": event.get("summary", "Untitled Event"),
            "start": event.get("start", {}).get("dateTime", ""),
        }
