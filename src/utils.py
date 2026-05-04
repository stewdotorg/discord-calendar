"""Utility functions — embed formatting, timezone conversion, error formatting."""

import datetime
import re
from zoneinfo import ZoneInfo

import dateparser
import discord
from googleapiclient.errors import HttpError

_INVALID_EMAIL_MSG = (
    "❌ Invalid email: {reason}. "
    "Please provide a valid email address, e.g. me@example.com."
)


def validate_email(email: str) -> str | None:
    """Validate basic email format.

    Returns an error message string if invalid, or None if valid.
    """
    if "@" not in email:
        return _INVALID_EMAIL_MSG.format(reason="missing '@'")
    _, domain = email.rsplit("@", 1)
    if "." not in domain:
        return _INVALID_EMAIL_MSG.format(reason="domain missing '.'")
    return None

# ── Mention resolution ─────────────────────────────────────────────────────

_MENTION_PATTERN = re.compile(r"^<@!?(\d+)>$")


def resolve_mentions(
    items: list[str],
    settings_store,
) -> tuple[list[str], list[str]]:
    """Resolve Discord @mentions to stored emails.

    Items that match the ``<@discord_id>`` pattern are looked up via
    ``settings_store.get(discord_id, "email")``.  Items that do not
    match are treated as raw email addresses and passed through unchanged.

    Args:
        items: List of strings — raw emails or Discord mentions.
        settings_store: A ``SettingsStore`` instance for email lookup.

    Returns:
        ``(resolved, warnings)`` tuple:

        * **resolved** — List of email addresses (resolved + passed-through).
          Unresolvable mentions with no stored email are omitted.
        * **warnings** — Warning messages for unresolvable mentions, suitable
          for display to the calling user.
    """
    resolved: list[str] = []
    warnings: list[str] = []

    for item in items:
        item = item.strip()
        match = _MENTION_PATTERN.match(item)
        if match:
            discord_id = match.group(1)
            email = settings_store.get(discord_id, "email")
            if email:
                resolved.append(email)
            else:
                warnings.append(
                    f"⚠️ Could not invite {item}: no email stored. "
                    "Ask them to run `/cal settings set email`"
                )
        else:
            # Treat as raw email/text — validation happens upstream.
            resolved.append(item)

    return resolved, warnings


EASTERN = ZoneInfo("America/New_York")

def format_datetime_eastern(dt: datetime.datetime) -> str:
    """Format a timezone-aware datetime in US Eastern 12-hour style.

    Args:
        dt: A timezone-aware datetime (any timezone).

    Returns:
        A string like 'May 1, 2026 at 2:00 PM'.
    """
    dt_eastern = dt.astimezone(EASTERN)
    month = dt_eastern.strftime("%B")
    day = dt_eastern.strftime("%d").lstrip("0")
    year = dt_eastern.strftime("%Y")
    time_str = dt_eastern.strftime("%I:%M %p").lstrip("0")
    return f"{month} {day}, {year} at {time_str}"


# ── when-param parsing ──────────────────────────────────────────────────────

# Time-of-day words → specific times for NLP expansion.
_TIME_OF_DAY_MAP = {
    "morning": "9am",
    "afternoon": "3pm",
    "evening": "6pm",
    "night": "9pm",
}


def _dateparser_now() -> datetime.datetime:
    """Return current timezone-aware UTC datetime.

    Extracted as a function so tests can patch it to pin the reference
    point for relative date expressions (e.g. "in 2 hours").
    """
    return datetime.datetime.now(datetime.timezone.utc)


def parse_when(when: str, tz: ZoneInfo = EASTERN) -> datetime.datetime:
    """Parse a `when` string into a timezone-aware UTC datetime.

    Uses dateparser for NLP date parsing (e.g. "tuesday at 3pm",
    "friday at noon", "in 2 hours", "May 1 3pm").

    All times are interpreted in *tz* (defaults to US Eastern),
    returned as UTC.

    Args:
        when: A natural-language or structured date/time string.
        tz: The timezone to interpret the input in (default: US Eastern).

    Returns:
        A timezone-aware UTC datetime.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    when_stripped = when.strip().strip('"\'')
    if not when_stripped:
        raise ValueError(
            "Expected date and time, e.g. 'May 1 3pm' or '2026-05-01 14:00'."
        )

    # ── Expand time-of-day words (morning→9am, etc.) ─────────────────────
    tokens = when_stripped.lower().split()
    expanded = [_TIME_OF_DAY_MAP.get(t, t) for t in tokens]
    processed = " ".join(expanded)

    # ── NLP dateparser ────────────────────────────────────────────────────
    dateparser_settings = {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": str(tz),
        "PREFER_DAY_OF_MONTH": "first",
        "RELATIVE_BASE": _dateparser_now().astimezone(tz),
        "RETURN_AS_TIMEZONE_AWARE": True,
    }
    parsed = dateparser.parse(processed, settings=dateparser_settings)
    if parsed is not None:
        return parsed.astimezone(datetime.timezone.utc)

    raise ValueError(
        f"Cannot parse '{when_stripped}'. "
        "Try 'May 1 3pm', 'tuesday 9am', '2026-05-01 14:00', "
        "or 'in 2 hours'."
    )


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


def format_edit_error(exc: HttpError) -> str:
    """Return a user-friendly error message for a Google Calendar edit error.

    Maps specific HTTP status codes to actionable messages.
    """
    status = exc.resp.status if exc.resp else 0

    messages = {
        403: (
            "❌ Permission denied — the bot does not have permission to "
            "edit events on this calendar."
        ),
        404: (
            "❌ Event not found — the event may have been deleted "
            "or the event ID is incorrect."
        ),
        429: (
            "⏳ Rate limited — too many requests. Please wait a moment "
            "and try again."
        ),
    }

    return messages.get(status, f"❌ Failed to edit event. ({status})")


def format_invite_error(exc: HttpError) -> str:
    """Return a user-friendly error message for an invite/attendee API error.

    Maps specific HTTP status codes to actionable messages.
    """
    status = exc.resp.status if exc.resp else 0

    messages = {
        403: (
            "❌ Cannot add attendees — the shared calendar does not allow "
            "the bot to modify attendee lists. This requires Domain-Wide "
            "Delegation of Authority for service accounts, or a calendar "
            "owned directly by the service account."
        ),
        404: (
            "❌ Event not found — the event may have been deleted "
            "or the event ID is incorrect."
        ),
        429: (
            "⏳ Rate limited — too many requests. Please wait a moment "
            "and try again."
        ),
    }

    return messages.get(status, f"❌ Failed to add attendees. ({status})")


def format_delete_error(exc: HttpError) -> str:
    """Return a user-friendly error message for a Google Calendar delete error.

    Maps specific HTTP status codes to actionable messages.
    """
    status = exc.resp.status if exc.resp else 0

    messages = {
        403: (
            "❌ Permission denied — the bot does not have permission to "
            "delete events from this calendar."
        ),
        404: (
            "❌ Event not found — the event may have already been deleted "
            "or the event ID is incorrect."
        ),
        429: (
            "⏳ Rate limited — too many requests. Please wait a moment "
            "and try again."
        ),
    }

    return messages.get(status, f"❌ Failed to delete event. ({status})")


def parse_minutes(minutes_str: str) -> list[int]:
    """Parse a comma-separated string of minutes into a list of ints.

    Args:
        minutes_str: Comma-separated integers, e.g. "10,30".

    Returns:
        A list of integer minutes values.

    Raises:
        ValueError: If any value is not a positive integer.
    """
    minutes_str = minutes_str.strip()
    if not minutes_str:
        raise ValueError("Minutes cannot be empty.")

    raw = [part.strip() for part in minutes_str.split(",")]
    result = []
    for part in raw:
        if not part:
            raise ValueError(
                f"Empty value in minutes: '{minutes_str}'. "
                "Use comma-separated integers, e.g. '10,30'."
            )
        try:
            val = int(part)
        except ValueError:
            raise ValueError(
                f"Invalid minutes value '{part}'. "
                "Use comma-separated integers, e.g. '10,30'."
            ) from None
        if val <= 0:
            raise ValueError(
                f"Minutes must be positive: {val}. "
                "Use values like 5, 10, 30, etc."
            )
        result.append(val)
    return result


def parse_date_eastern(date_str: str) -> datetime.datetime:
    """Parse a YYYY-MM-DD date string in US Eastern as a UTC datetime.

    Interprets the date at midnight US Eastern time and converts to UTC.
    Used by /cal list for from/to date range parameters.

    Args:
        date_str: A date string in YYYY-MM-DD format (e.g. '2026-05-15').

    Returns:
        A timezone-aware UTC datetime at midnight Eastern for that date.

    Raises:
        ValueError: If the string is not in YYYY-MM-DD format or the
            date is invalid.
    """
    try:
        dt_eastern = datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date '{date_str}'. Expected YYYY-MM-DD format."
        ) from None
    dt_eastern = dt_eastern.replace(tzinfo=EASTERN)
    return dt_eastern.astimezone(datetime.timezone.utc)


def get_today_eastern_range() -> tuple[datetime.datetime, datetime.datetime]:
    """Return (start_of_today_utc, end_of_today_utc) covering today in US Eastern.

    Returns timezone-aware UTC datetimes.
    """
    now_eastern = _dateparser_now().astimezone(EASTERN)
    start_eastern = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
    end_eastern = start_eastern + datetime.timedelta(days=1)

    start_utc = start_eastern.astimezone(datetime.timezone.utc)
    end_utc = end_eastern.astimezone(datetime.timezone.utc)

    return start_utc, end_utc


def _format_time_range_eastern(start_str: str, end_str: str) -> str:
    """Format a time range in US Eastern 12-hour time.

    Args:
        start_str: ISO 8601 start datetime string.
        end_str: ISO 8601 end datetime string.

    Returns:
        A string like '3:00–4:30 PM ET' or '?' when times are missing.
    """
    if not start_str or not end_str:
        return "?"

    dt_start = datetime.datetime.fromisoformat(start_str)
    dt_end = datetime.datetime.fromisoformat(end_str)

    start_eastern = dt_start.astimezone(EASTERN)
    end_eastern = dt_end.astimezone(EASTERN)

    fmt = "%I:%M"
    start_fmt = start_eastern.strftime(fmt).lstrip("0")
    end_fmt = end_eastern.strftime(fmt).lstrip("0")

    # Show AM/PM once if both are the same, otherwise on each
    start_ampm = start_eastern.strftime("%p")
    end_ampm = end_eastern.strftime("%p")

    if start_ampm == end_ampm:
        return f"{start_fmt}–{end_fmt} {start_ampm} ET"
    else:
        return f"{start_fmt} {start_ampm}–{end_fmt} {end_ampm} ET"


def format_events_embed(
    events: list[dict], date_title: str = "Today"
) -> discord.Embed:
    """Build a Discord embed that lists calendar events.

    Args:
        events: List of Google Calendar event dicts.
        date_title: Human-readable date for the embed title
                    (e.g. 'April 28, 2026'). Defaults to 'Today'.

    Returns:
        A discord.Embed with events formatted as fields.
    """
    embed = discord.Embed(
        title=f"Events for {date_title}",
        color=discord.Color.blue(),
    )

    if not events:
        embed.description = "No events scheduled for today."
        return embed

    for event in events:
        summary = event.get("summary", "Untitled Event")
        start_str = event.get("start", {}).get("dateTime", "")
        end_str = event.get("end", {}).get("dateTime", "")
        html_link = event.get("htmlLink", "")

        time_range = _format_time_range_eastern(start_str, end_str)

        value_lines = [f"**When:** {time_range}"]
        if html_link:
            value_lines.append(f"[Open in Google Calendar]({html_link})")

        embed.add_field(
            name=summary,
            value="\n".join(value_lines),
            inline=False,
        )

    return embed
