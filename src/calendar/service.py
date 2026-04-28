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
                service.calendarList()
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

    def list_events(
        self,
        time_min: datetime.datetime,
        time_max: datetime.datetime,
        max_results: int = 250,
    ) -> list[dict]:
        """List events in a time range.

        Args:
            time_min: Start of the time range (timezone-aware datetime).
            time_max: End of the time range (timezone-aware datetime).
            max_results: Maximum number of events to return.

        Returns:
            List of event dicts as returned by the Google Calendar API,
            ordered by start time.

        Raises:
            RuntimeError: If the API call fails.
        """
        service = self._build_service()
        try:
            result = (
                service.events()
                .list(
                    calendarId=self._calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                )
                .execute()
            )
        except HttpError as exc:
            msg = f"Failed to list events ({self._calendar_id}): {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc

        return result.get("items", [])
