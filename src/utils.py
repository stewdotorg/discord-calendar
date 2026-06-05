"""Utility functions — embed formatting, timezone conversion, error formatting."""

import datetime
import re
from zoneinfo import ZoneInfo

import dateparser
import discord
from googleapiclient.errors import HttpError

from src.db.queries import SettingsStore

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
    settings_store: SettingsStore,
) -> tuple[list[str], list[str], set[str]]:
    """Resolve Discord @mentions to stored emails.

    Items that match the ``<@discord_id>`` pattern are looked up via
    ``settings_store.get(discord_id, "email")``.  Items that do not
    match are treated as raw email addresses and passed through unchanged.

    Args:
        items: List of strings — raw emails or Discord mentions.
        settings_store: A ``SettingsStore`` instance for email lookup.

    Returns:
        ``(resolved, warnings, unresolvable_ids)`` tuple:

        * **resolved** — List of email addresses (resolved + passed-through).
          Unresolvable mentions with no stored email are omitted.
        * **warnings** — Warning messages for unresolvable mentions, suitable
          for display to the calling user.
        * **unresolvable_ids** — Set of Discord user IDs for mentions that
          could not be resolved to an email (for DM follow-up).
    """
    resolved: list[str] = []
    warnings: list[str] = []
    unresolvable_ids: set[str] = set()

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
                    f"⚠️ Could not invite {item} — they have been prompted to set up their email."
                )
                unresolvable_ids.add(discord_id)
        else:
            # If it starts with @ but isn't a valid mention, it's a typoed handle.
            if item.startswith("@"):
                warnings.append(
                    f"⚠️ {item}: user not found. "
                    "Check the spelling or use their email address instead."
                )
            else:
                # Treat as raw email/text — validation happens upstream.
                resolved.append(item)

    return resolved, warnings, unresolvable_ids


EASTERN = ZoneInfo("America/New_York")
DEFAULT_TIMEZONE = EASTERN  # Canonical default for per-user timezone lookups


def get_user_timezone(interaction: discord.Interaction) -> ZoneInfo:
    """Resolve a user's configured timezone from settings.

    Falls back to DEFAULT_TIMEZONE if no timezone is stored or the stored
    value is invalid.

    Args:
        interaction: The Discord interaction (used to access the settings store).

    Returns:
        A ZoneInfo for the user's configured timezone, or DEFAULT_TIMEZONE.
    """
    user_id = str(interaction.user.id)
    settings = interaction.client.settings  # type: ignore[attr-defined]
    tz_str = settings.get(user_id, "timezone")
    try:
        return ZoneInfo(tz_str) if tz_str else DEFAULT_TIMEZONE
    except (KeyError, ValueError, TypeError):
        return DEFAULT_TIMEZONE

def format_datetime_eastern(
    dt: datetime.datetime,
    tz: ZoneInfo = EASTERN,
) -> str:
    """Format a timezone-aware datetime in the given timezone 12-hour style.

    Args:
        dt: A timezone-aware datetime (any timezone).
        tz: The timezone to display in (default US Eastern).

    Returns:
        A string like 'May 1, 2026 at 2:00 PM'.
    """
    dt_local = dt.astimezone(tz)
    month = dt_local.strftime("%B")
    day = dt_local.strftime("%d").lstrip("0")
    year = dt_local.strftime("%Y")
    time_str = dt_local.strftime("%I:%M %p").lstrip("0")
    return f"{month} {day}, {year} at {time_str}"


# ── when-param parsing ──────────────────────────────────────────────────────

# Time-of-day words → specific times for NLP expansion.
_TIME_OF_DAY_MAP = {
    "morning": "9am",
    "afternoon": "3pm",
    "evening": "6pm",
    "night": "9pm",
}

# ── Duration detection regexes ──────────────────────────────────────────

# Matches a dash-separated time range at the end of a when string.
# Captures date prefix, start time, and end time.
# e.g. "tomorrow 9-11" → prefix="tomorrow", t1="9", t2="11"
_DURATION_DASH_RE = re.compile(
    r'^(.+?\s)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*[-–]\s*'
    r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)$',
    re.IGNORECASE,
)

# Matches a "to"-separated time range (case-insensitive, word boundary).
# e.g. "tomorrow 4 to 6pm" → left="tomorrow 4", right="6pm"
_DURATION_TO_RE = re.compile(
    r'^(.+?)\s+to\s+(.+?)$',
    re.IGNORECASE,
)

# Splits a combined date+time string into date prefix and time part.
# e.g. "tomorrow 4" → ("tomorrow", "4")
_SPLIT_DATE_TIME_RE = re.compile(
    r'^(.+)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)$',
    re.IGNORECASE,
)

# Detects explicit AM/PM in a time string.
_AMPM_RE = re.compile(r'\d\s*(am|pm)\b', re.IGNORECASE)

# Appends AM/PM to the last time-like token in a string,
# and extracts the hour from it.
_APPEND_PERIOD_RE = re.compile(r'(\d{1,2}(?::\d{2})?)\s*$')


def _dateparser_now() -> datetime.datetime:
    """Return current timezone-aware UTC datetime.

    Extracted as a function so tests can patch it to pin the reference
    point for relative date expressions (e.g. "in 2 hours").
    """
    return datetime.datetime.now(datetime.timezone.utc)


def _extract_am_pm(time_str: str) -> str | None:
    """Return 'am' or 'pm' if *time_str* has an explicit AM/PM indicator."""
    m = _AMPM_RE.search(time_str)
    return m.group(1).lower() if m else None


def _extract_hour(time_str: str) -> int | None:
    """Extract the hour from the last time-like token in *time_str*.

    Looks for a 1-2 digit hour (optionally followed by ``:mm``) at
    the end of the string, so it does not pick up digits from date
    components like "May 3" or "2026-05-01".
    """
    m = _APPEND_PERIOD_RE.search(time_str)
    if m:
        digits = m.group(1).split(":")[0]
        return int(digits)
    return None


def _infer_period(hour: int) -> str:
    """Infer AM/PM from an hour value.

    9–11 → AM,  everything else (12, 1–8) → PM.
    """
    return "am" if hour in (9, 10, 11) else "pm"


def _apply_period(s: str, period: str) -> str:
    """Append *period* ("am" or "pm") to the last time-like token in *s*.

    e.g. "tomorrow 10" + "am" → "tomorrow 10am"
         "tomorrow 10:30" + "pm" → "tomorrow 10:30pm"
    """
    return _APPEND_PERIOD_RE.sub(rf"\1{period}", s)


def _dateparser_parse(when_str: str, tz: ZoneInfo) -> datetime.datetime:
    """Parse *when_str* with dateparser and return a UTC datetime.

    Raises ValueError on failure.
    """
    dateparser_settings = {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": str(tz),
        "PREFER_DAY_OF_MONTH": "first",
        "RELATIVE_BASE": _dateparser_now().astimezone(tz),
        "RETURN_AS_TIMEZONE_AWARE": True,
    }
    parsed = dateparser.parse(when_str, settings=dateparser_settings)
    if parsed is not None:
        return parsed.astimezone(datetime.timezone.utc)
    raise ValueError(
        f"Cannot parse '{when_str}'. "
        "Try 'May 1 3pm', 'tuesday 9am', '2026-05-01 14:00', "
        "or 'in 2 hours'."
    )


def parse_when(
    when: str, tz: ZoneInfo = EASTERN,
) -> "datetime.datetime | tuple[datetime.datetime, datetime.datetime]":
    """Parse a `when` string into a timezone-aware UTC datetime.

    Detects duration / time-range expressions (using ``-`` or ``to``
    separator) and returns a ``(start, end)`` tuple.  Applies AM/PM
    inference for ambiguous times following these rules:

    * 9, 10, 11 → AM;  12, 1–8 → PM
    * When only one side has an explicit AM/PM the other inherits it.
    * When neither side is explicit each is inferred independently.

    Non-range inputs return a single ``datetime``.

    Args:
        when: A natural-language or structured date/time string.
        tz: The timezone to interpret the input in (default: US Eastern).

    Returns:
        A single UTC ``datetime`` or a ``(start, end)`` tuple.

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

    # ── Duration detection ───────────────────────────────────────────────
    parts = _detect_duration(processed)
    if parts is not None:
        date_prefix, start_time, end_time = parts
        return _parse_duration(date_prefix, start_time, end_time, tz)

    # ── Single datetime (non-range) ──────────────────────────────────────
    return _parse_single(processed, tz)


def _detect_duration(
    when: str,
) -> tuple[str, str, str] | None:
    """Detect a duration / time-range expression in *when*.

    Returns ``(date_prefix, start_time, end_time)`` if a range is found,
    or ``None`` if *when* is a single datetime expression.
    """
    # Try "to" separator first (case-insensitive, word boundary).
    m = _DURATION_TO_RE.match(when)
    if m:
        left = m.group(1).strip()
        right = m.group(2).strip()
        dm = _SPLIT_DATE_TIME_RE.match(left)
        if dm:
            return (dm.group(1).strip(), dm.group(2).strip(), right)
        # Fallback: treat entire left as date prefix, right as time
        return (left, "", right)

    # Try dash separator.
    m = _DURATION_DASH_RE.match(when)
    if m:
        prefix = (m.group(1) or "").strip()
        t1 = m.group(2).strip()
        t2 = m.group(3).strip()
        return (prefix, t1, t2)

    return None


def _parse_single(
    when: str, tz: ZoneInfo, *, force_period: str | None = None,
) -> datetime.datetime:
    """Parse a single datetime string with optional AM/PM inference.

    If *when* has no explicit AM/PM indicator and contains a bare
    hour that looks like a time (not pure date), the period is inferred
    from the hour (9–11→AM, 12,1–8→PM).  *force_period* overrides the
    inferred period (used when one side of a duration range inherits
    from the other).
    """
    explicit = _extract_am_pm(when)
    if explicit is None:
        period = force_period
        if period is None:
            hour = _extract_hour(when)
            # Only infer if there is a time-like token at the end
            # (bare hour digits, not embedded in a date like "05/06/2026"),
            # and the hour is 1–12 (skip 24-hour times like "14:00").
            if hour is not None and 1 <= hour <= 12 and _has_time_token(when):
                period = _infer_period(hour)
        if period and _has_time_token(when):
            when = _apply_period(when, period)

    return _dateparser_parse(when, tz)


def _has_time_token(when: str) -> bool:
    """Check whether *when* ends with a time-like token (hour or hour:min).

    Returns False for pure-date strings like "05/06/2026" or
    "2026-05-01" so that AM/PM inference is not applied to them.
    """
    # A time token is: bare digits (1-2 digits or H:MM) at the end,
    # optionally followed by am/pm.  Not embedded in a date pattern.
    return bool(re.search(
        r'(?:\s|^)(\d{1,2}(?::\d{2})?)\s*(?:am|pm)?\s*$',
        when, re.IGNORECASE,
    ))


def _parse_duration(
    date_prefix: str,
    start_time: str,
    end_time: str,
    tz: ZoneInfo,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Parse a duration / time-range expression.

    AM/PM inference rules:
    * If both sides have explicit AM/PM → use as-is.
    * If only one side is explicit → the other inherits its period.
    * If neither is explicit → infer start from hour (9-11→AM, rest→PM),
      end inherits start's period.

    After parsing, if the end falls before the start (chronological
    inversion, e.g. "11-1" inheriting AM gives 1am before 11am), add
    12 hours to the end.

    Args:
        date_prefix: The date portion (e.g. "tomorrow", "friday", "may 1").
        start_time: The start time expression (e.g. "9", "10:30", "4pm").
        end_time: The end time expression (e.g. "11", "11:45", "6pm").
        tz: The timezone to interpret in.

    Returns:
        A ``(start, end)`` tuple of timezone-aware UTC datetimes.
    """
    start_explicit = _extract_am_pm(start_time)
    end_explicit = _extract_am_pm(end_time)

    # Determine periods for each side.
    if start_explicit and end_explicit:
        start_period: str | None = start_explicit
        end_period: str | None = end_explicit
    elif start_explicit:
        start_period = start_explicit
        end_period = start_explicit  # inherit
    elif end_explicit:
        start_period = end_explicit  # inherit
        end_period = end_explicit
    else:
        # Neither explicit — infer start, end inherits.
        start_hour = _extract_hour(start_time)
        start_period = _infer_period(start_hour) if start_hour else None
        end_period = start_period  # inherit from start

    # Build full parse strings (date_prefix + time).
    start_full = f"{date_prefix} {start_time}".strip()
    end_full = f"{date_prefix} {end_time}".strip()

    start_dt = _parse_single(start_full, tz, force_period=start_period)
    end_dt = _parse_single(end_full, tz, force_period=end_period)

    # Chronological adjustment: if the end falls before or at the start
    # (e.g. "11-1" inheriting AM → 11am–1am), add 12 hours.
    if end_dt <= start_dt:
        end_dt = end_dt + datetime.timedelta(hours=12)

    return (start_dt, end_dt)


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


def parse_date_eastern(date_str: str, tz: ZoneInfo = EASTERN) -> datetime.datetime:
    """Parse a YYYY-MM-DD date string in the given timezone as a UTC datetime.

    Interprets the date at midnight in the given timezone and converts to UTC.
    Used by /cal list for from/to date range parameters.

    Args:
        date_str: A date string in YYYY-MM-DD format (e.g. '2026-05-15').
        tz: The timezone to interpret the date in (default US Eastern).

    Returns:
        A timezone-aware UTC datetime at midnight in the given timezone for
        that date.

    Raises:
        ValueError: If the string is not in YYYY-MM-DD format or the
            date is invalid.
    """
    try:
        dt_parsed = datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date '{date_str}'. Expected YYYY-MM-DD format."
        ) from None
    dt_parsed = dt_parsed.replace(tzinfo=tz)
    return dt_parsed.astimezone(datetime.timezone.utc)


def get_today_eastern_range(
    tz: ZoneInfo = EASTERN,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Return (start_of_today_utc, end_of_today_utc) covering today in the given
    timezone.

    Returns timezone-aware UTC datetimes.
    """
    now_local = _dateparser_now().astimezone(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + datetime.timedelta(days=1)

    start_utc = start_local.astimezone(datetime.timezone.utc)
    end_utc = end_local.astimezone(datetime.timezone.utc)

    return start_utc, end_utc


def _format_time_range_eastern(
    start_str: str, end_str: str, tz: ZoneInfo = EASTERN
) -> str:
    """Format a time range in the given timezone 12-hour time.

    Args:
        start_str: ISO 8601 start datetime string.
        end_str: ISO 8601 end datetime string.
        tz: The timezone to display in (default US Eastern).

    Returns:
        A string like '3:00–4:30 PM ET' or '?' when times are missing.
    """
    if not start_str or not end_str:
        return "?"

    dt_start = datetime.datetime.fromisoformat(start_str)
    dt_end = datetime.datetime.fromisoformat(end_str)

    start_local = dt_start.astimezone(tz)
    end_local = dt_end.astimezone(tz)

    fmt = "%I:%M"
    start_fmt = start_local.strftime(fmt).lstrip("0")
    end_fmt = end_local.strftime(fmt).lstrip("0")

    # Show AM/PM once if both are the same, otherwise on each
    start_ampm = start_local.strftime("%p")
    end_ampm = end_local.strftime("%p")

    if start_ampm == end_ampm:
        return f"{start_fmt}–{end_fmt} {start_ampm} ET"
    else:
        return f"{start_fmt} {start_ampm}–{end_fmt} {end_ampm} ET"


def format_events_embed(
    events: list[dict],
    date_title: str = "Today",
    tz: ZoneInfo = EASTERN,
) -> discord.Embed:
    """Build a Discord embed that lists calendar events.

    Args:
        events: List of Google Calendar event dicts.
        date_title: Human-readable date for the embed title
                    (e.g. 'April 28, 2026'). Defaults to 'Today'.
        tz: The timezone to display event times in (default US Eastern).

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

        time_range = _format_time_range_eastern(start_str, end_str, tz=tz)

        value_lines = [f"**When:** {time_range}"]
        if html_link:
            value_lines.append(f"[Open in Google Calendar]({html_link})")

        embed.add_field(
            name=summary,
            value="\n".join(value_lines),
            inline=False,
        )

    return embed
