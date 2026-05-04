"""Shared autocomplete callback for event selection.

Provides ``event_autocomplete``, used by /cal delete, /cal edit, /cal invite,
/cal reminders set, and /cal reminders show to provide fast event suggestions.

Includes a module-level 30-second TTL cache to avoid hitting the Google
Calendar API on every keystroke.
"""

import datetime
import logging
import time
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from src.utils import EASTERN, get_user_timezone

logger = logging.getLogger(__name__)

TRUNCATE_AT = 100
_CACHE_TTL = 30.0  # seconds

# Module-level cache: dict keyed on calendar_id → (timestamp, event_list)
_event_cache: dict[str, tuple[float, list[dict]]] = {}


def _truncate_for_autocomplete(title: str) -> str:
    """Truncate an event title for display in the autocomplete dropdown.

    Discord choice names are limited to 100 characters.
    """
    if len(title) <= TRUNCATE_AT:
        return title
    return title[: TRUNCATE_AT - 1] + "…"


def _format_autocomplete_label(event: dict, tz: ZoneInfo = EASTERN) -> str:
    """Format an event as a choice label: 'May 2, 4pm — BBQ'.

    Includes minutes only when not :00, e.g. 'May 2, 4:30pm — Standup'.
    """
    summary = event.get("summary", "Untitled Event")
    start_str = event.get("start", {}).get("dateTime", "")

    date_part = ""
    if start_str:
        try:
            dt = datetime.datetime.fromisoformat(start_str)
            dt_local = dt.astimezone(tz)
            month = dt_local.strftime("%b")
            day = dt_local.strftime("%d").lstrip("0")
            minute = dt_local.minute
            hour = dt_local.hour
            ampm = "am" if hour < 12 else "pm"
            display_hour = hour % 12
            if display_hour == 0:
                display_hour = 12

            if minute == 0:
                date_part = f"{month} {day}, {display_hour}{ampm}"
            else:
                date_part = f"{month} {day}, {display_hour}:{minute:02d}{ampm}"
        except (ValueError, OverflowError):
            pass

    if date_part:
        label = f"{date_part} — {summary}"
    else:
        label = summary

    return _truncate_for_autocomplete(label)


async def event_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete callback — queries Google Calendar for upcoming events
    and filters by the user's typed substring.

    Uses a 30-second TTL cache to avoid API calls on every keystroke.
    ``time_min`` is set to the start of today in UTC, so ongoing
    events still appear in the autocomplete dropdown.
    Event labels are formatted in the user's timezone.
    """
    calendar_service = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar_service is None:
        return []

    calendar_id = getattr(calendar_service, "_calendar_id", "default")

    user_tz = get_user_timezone(interaction)

    now_ts = time.time()
    cached = _event_cache.get(calendar_id)
    if cached is not None:
        cached_ts, cached_events = cached
        if now_ts - cached_ts < _CACHE_TTL:
            return _filter_and_format_choices(cached_events, current, user_tz)

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    time_min = utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = time_min + datetime.timedelta(days=14)

    try:
        events = calendar_service.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=25,
        )
    except RuntimeError:
        logger.warning("Autocomplete list_events failed — returning empty")
        return []

    _event_cache[calendar_id] = (now_ts, events)

    return _filter_and_format_choices(events, current, user_tz)


def _filter_and_format_choices(
    events: list[dict],
    current: str,
    tz: ZoneInfo = EASTERN,
) -> list[app_commands.Choice[str]]:
    """Filter events by query substring and format as Discord choices.

    Returns at most 25 choices (Discord's autocomplete limit).
    """
    query = current.strip().lower()

    choices: list[app_commands.Choice[str]] = []
    for event in events:
        summary = event.get("summary", "Untitled Event")
        if query and query not in summary.lower():
            continue
        label = _format_autocomplete_label(event, tz=tz)
        choices.append(app_commands.Choice(name=label, value=event["id"]))

    return choices[:25]
