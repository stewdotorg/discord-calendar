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

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Words stripped before dateparser ("tuesday" already means next tuesday).
_DATEWORDS_TO_STRIP = {"next", "this", "at", "on"}

# Pattern for relative time offsets like "in 5 hours" or "in 30 minutes".
_RELATIVE_TIME_PATTERN = re.compile(
    r"\bin\s+(\d+)\s*(hours?|hrs?|h|minutes?|mins?)\b"
)

# Time-of-day words → specific times for NLP expansion.
_TIME_OF_DAY_MAP = {
    "morning": "9am",
    "afternoon": "3pm",
    "evening": "6pm",
    "night": "9pm",
}


def _dateparser_now() -> datetime.datetime:
    """Return current timezone-aware UTC datetime (extracted for testability).

    Tests patch this to pin the reference point for relative dates.
    Must be timezone-aware so dateparser does not misinterpret the
    value via TIMEZONE when RELATIVE_BASE is naive.
    """
    return datetime.datetime.now(datetime.timezone.utc)


def parse_when(when: str) -> datetime.datetime:
    """Parse a `when` string into a timezone-aware UTC datetime.

    Uses dateparser for NLP date parsing (e.g. "next tuesday at 3pm",
    "friday at noon", "in 2 hours"), falling back to manual patterns
    (e.g. "2026-05-01 14:00", "5/1 3pm", "May 1 3pm", "today 9am").

    All times are interpreted as US Eastern, returned as UTC.

    Args:
        when: A natural-language or structured date/time string.

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

    # ── Strip filler words and expand time-of-day words ─────────────────────
    tokens = when_stripped.lower().split()
    filtered = [t for t in tokens if t not in _DATEWORDS_TO_STRIP]
    expanded = [_TIME_OF_DAY_MAP.get(t, t) for t in filtered]
    processed = " ".join(expanded)

    # ── Short-circuit: "today" / "tomorrow" go to manual parser ────────────
    # dateparser can misinterpret the hour when RELATIVE_BASE is tz-aware
    # UTC and the time expression has no explicit zone (e.g. "today 9:00").
    # The manual parser always treats times as US Eastern, so route these
    # unambiguous patterns there directly (after time-of-day expansion).
    first_word = processed.split()[0] if processed.split() else ""
    if first_word in ("today", "tomorrow"):
        return _parse_when_manual(processed)

    # ── Try NLP dateparser ──────────────────────────────────────────────────
    dateparser_settings = {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": "US/Eastern",
        "PREFER_DAY_OF_MONTH": "first",
        "RELATIVE_BASE": _dateparser_now(),
        "RETURN_AS_TIMEZONE_AWARE": True,
    }
    parsed = dateparser.parse(processed, settings=dateparser_settings)
    if parsed is not None:
        return parsed.astimezone(datetime.timezone.utc)

    # ── Try stripping "in X hours/minutes" and reparsing ──────────────────
    # Relative-offset extraction also exists at the top of _parse_when_manual
    # (needed for the "today"/"tomorrow" short-circuit path above).  Both
    # sites feed into the same manual parser, just from different entry points.
    remainder, offset = _extract_relative_offset(processed)
    if offset is not None:
        if not remainder:
            # Standalone relative: "in 2 hours" → now + offset
            return _dateparser_now() + offset

        # Try dateparser on the remainder, then manual parser
        parsed = dateparser.parse(remainder, settings=dateparser_settings)
        if parsed is not None:
            return (parsed + offset).astimezone(datetime.timezone.utc)

        try:
            return _parse_when_manual(remainder) + offset
        except ValueError:
            pass

    # ── Fall back to manual patterns ────────────────────────────────────────
    return _parse_when_manual(when_stripped)


def _extract_relative_offset(when_str: str) -> tuple[str, datetime.timedelta | None]:
    """Extract 'in X hours/minutes' from *when_str*.

    Returns (remainder_without_offset, timedelta) or (original, None)
    if no relative time pattern is found.
    """
    m = _RELATIVE_TIME_PATTERN.search(when_str)
    if not m:
        return when_str, None

    amount = int(m.group(1))
    unit = m.group(2)

    if unit[0] == "h":
        delta = datetime.timedelta(hours=amount)
    else:
        delta = datetime.timedelta(minutes=amount)

    remainder = (when_str[: m.start()] + when_str[m.end() :]).strip()
    remainder = " ".join(remainder.split())  # collapse whitespace

    return remainder, delta


def _parse_when_manual(when_stripped: str) -> datetime.datetime:
    """Fallback manual parser for structured date/time patterns.

    Supports:
      - "YYYY-MM-DD HH:MM"        (24-hour time)
      - "MM/DD HH:MM[am|pm]"      (US date, 12-hour optional suffix)
      - "Month DD HH:MM[am|pm]"   (e.g. "May 1 3pm" or "May 1 15:00")
      - "today HH:MM[am|pm]"
      - "tomorrow HH:MM[am|pm]"
      - "<date> in X hours/minutes" (relative time offset)
      - "in X hours/minutes" (standalone relative from now)
    """
    now_eastern = _dateparser_now().astimezone(EASTERN)

    # ── Extract relative time offset ("in X hours/minutes") ──────────────
    remainder, offset = _extract_relative_offset(when_stripped.lower())
    if offset is not None:
        if not remainder:
            # Standalone relative: "in 2 hours" → now + offset
            dt_eastern = now_eastern + offset
            return dt_eastern.astimezone(datetime.timezone.utc)
        # Combined: "today in 5 hours" → parse "today", add offset
        return _parse_when_manual(remainder) + offset

    # Try ISO-like: YYYY-MM-DD HH:MM
    iso_match = re.match(
        r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})",
        when_stripped,
    )
    if iso_match:
        year, month, day, hour, minute = [int(g) for g in iso_match.groups()]
        dt_eastern = datetime.datetime(year, month, day, hour, minute,
                                       tzinfo=EASTERN)
        return dt_eastern.astimezone(datetime.timezone.utc)

    parts = when_stripped.split()
    if len(parts) < 2:
        # Bare date keywords — reached by recursive calls after stripping a
        # relative offset (e.g. "today in 5 hours" → _parse_when_manual("today")).
        joined = when_stripped.strip().lower()
        if joined == "today":
            dt_eastern = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
            return dt_eastern.astimezone(datetime.timezone.utc)
        if joined == "tomorrow":
            tomorrow = now_eastern + datetime.timedelta(days=1)
            dt_eastern = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            return dt_eastern.astimezone(datetime.timezone.utc)
        raise ValueError(
            "Expected date and time, e.g. 'May 1 3pm' or '2026-05-01 14:00'."
        )

    # Time is in the last 1-2 tokens (e.g. "3pm" or "3:00 pm")
    parsed_time = _parse_time_eastern(tuple(parts[-2:]))
    if parsed_time is not None:
        day_date_parts = parts[:-2]
    else:
        parsed_time = _parse_time_eastern((parts[-1],))
        if parsed_time is not None:
            day_date_parts = parts[:-1]
        else:
            raise ValueError(
                f"Cannot parse time from '{' '.join(parts[-2:])}'. "
                "Use HH:MM (24h) or H:MMam/pm (12h)."
            )

    # Parse the date part (skip filler words like "at", "on")
    day_date_parts = [p for p in day_date_parts if p.lower() not in ("at", "on")]
    year, month, day = _parse_date_part(day_date_parts, now_eastern)

    hour, minute = parsed_time
    dt_eastern = datetime.datetime(year, month, day, hour, minute,
                                   tzinfo=EASTERN)
    return dt_eastern.astimezone(datetime.timezone.utc)


def _parse_time_eastern(parts: tuple[str, ...]) -> tuple[int, int] | None:
    """Parse time tokens like ("3pm",) or ("3:00", "pm") into (hour, minute).

    Returns None if the tokens don't look like a time.
    """
    joined = " ".join(parts).strip().lower()

    # Try HH:MM (24-hour)
    m = re.match(r"^(\d{1,2}):(\d{2})$", joined)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)
        return None

    # Try H:MMam or H:MMpm or Ham or Hpm
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", joined)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if hour < 1 or hour > 12 or minute > 59:
            return None
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        return (hour, minute)

    return None


def _parse_date_part(parts: list[str],
                     now_eastern: datetime.datetime) -> tuple[int, int, int]:
    """Parse date tokens into (year, month, day).

    Supports:
      - "today" / "tomorrow"
      - "MM/DD" (US format)
      - "Month DD" (e.g. "May 1")
    """
    if not parts:
        raise ValueError("Missing date. Use 'today', 'tomorrow', 'MM/DD', "
                         "or 'Month DD'.")

    joined = " ".join(parts).strip().lower()

    if joined == "today":
        return (now_eastern.year, now_eastern.month, now_eastern.day)

    if joined == "tomorrow":
        tomorrow = now_eastern + datetime.timedelta(days=1)
        return (tomorrow.year, tomorrow.month, tomorrow.day)

    # Try MM/DD
    m = re.match(r"^(\d{1,2})/(\d{1,2})$", joined)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (now_eastern.year, month, day)
        raise ValueError(f"Invalid date: {joined}")

    # Try Month DD
    if len(parts) == 2:
        month_name = parts[0].lower()
        month = _MONTH_NAMES.get(month_name)
        if month is None:
            raise ValueError(f"Unknown month '{parts[0]}'. "
                             "Use full or abbreviated month name.")
        try:
            day = int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid day '{parts[1]}'.")
        if day < 1 or day > 31:
            raise ValueError(f"Invalid day {day}.")
        return (now_eastern.year, month, day)

    raise ValueError(
        f"Cannot parse date '{joined}'. "
        "Use 'today', 'tomorrow', 'MM/DD', or 'Month DD'."
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


def format_rsvp_error(exc: HttpError) -> str:
    """Return a user-friendly error message for an RSVP/invite API error.

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


# ── @mention resolution ─────────────────────────────────────────────────────

_MENTION_PATTERN = re.compile(r"^<@!?(\d+)>$")


def resolve_mentions(invite_str: str, email_lookup) -> tuple[list[str], list[str]]:
    """Resolve Discord mentions in a comma-separated invite string to emails.

    Splits *invite_str* on commas, trims whitespace, and processes each item:

    * ``<@123456789>`` or ``<@!123456789>`` — looked up via *email_lookup*.
      If an email is found it is added to the resolved list; otherwise a
      warning is emitted.
    * Everything else — treated as a raw email address and validated with
      :func:`validate_email`.  Valid addresses pass through unchanged;
      invalid items produce a warning.

    Args:
        invite_str: Comma-separated list of Discord mentions and/or raw
            email addresses (e.g. ``"<@123>, alice@example.com"``).
        email_lookup: Callable that takes a Discord user ID string and
            returns the stored email (``str | None``).

    Returns:
        ``(emails, warnings)`` tuple:

        * *emails* — list of validated/resolved email addresses ready for
          :meth:`CalendarService.add_attendees`.
        * *warnings* — list of human-readable warning messages about
          unresolvable users or invalid emails.
    """
    if not invite_str or not invite_str.strip():
        return [], []

    items = [item.strip() for item in invite_str.split(",")]
    emails: list[str] = []
    warnings: list[str] = []

    for item in items:
        if not item:
            continue

        mention_match = _MENTION_PATTERN.match(item)
        if mention_match:
            discord_id = mention_match.group(1)
            email = email_lookup(discord_id)
            if email:
                if email not in emails:
                    emails.append(email)
            else:
                warnings.append(
                    f"⚠️ Could not invite <@{discord_id}>: no email stored. "
                    "Ask them to run `/cal settings email-set`."
                )
        else:
            error = validate_email(item)
            if error:
                warnings.append(error)
            else:
                if item not in emails:
                    emails.append(item)

    return emails, warnings


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
