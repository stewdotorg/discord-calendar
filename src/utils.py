"""Shared utilities — error formatting, timezone handling, Discord embeds."""

from googleapiclient.errors import HttpError


def format_create_error(exc: HttpError) -> str:
    """Return a user-friendly error message for a Google Calendar API error.

    Maps specific HTTP status codes to actionable messages.
    """
    status = exc.resp.status if exc.resp else 0

    messages = {
        403: (
            "❌ Permission denied — the bot does not have write access to "
            "the calendar. Ask an admin to grant the service account "
            "'Make changes to events' permission."
        ),
        404: (
            "❌ Calendar not found — the configured calendar may have been "
            "deleted or the ID in `.env` is incorrect."
        ),
        429: (
            "⏳ Rate limited — too many requests. Please wait a moment "
            "and try again."
        ),
    }

    return messages.get(status, f"❌ Failed to create event. ({status})")
