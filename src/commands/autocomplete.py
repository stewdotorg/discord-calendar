"""Shared autocomplete callback for event selection.

Provides ``event_autocomplete``, used by /cal delete, /cal edit, /cal invite,
/cal reminders set, and /cal reminders show to provide fast event suggestions.

Includes a module-level 30-second TTL cache to avoid hitting the Google
Calendar API on every keystroke.
"""

import datetime
import logging
import time

import discord
from discord import app_commands

from src.utils import EASTERN

logger = logging.getLogger(__name__)

TRUNCATE_AT = 100
_CACHE_TTL = 30.0  # seconds

# Module-level cache: dict keyed on (calendar_id,) → (timestamp, event_list)
_event_cache: dict[tuple[str, ...], tuple[float, list[dict]]] = {}


def _truncate_for_autocomplete(title: str) -> str:
    """Truncate an event title for display in the autocomplete dropdown.

    Discord choice names are limited to 100 characters.
    """
    if len(title) <= TRUNCATE_AT:
        return title
    return title[: TRUNCATE_AT - 1] + "…"


def _format_autocomplete_label(event: dict) -> str:
    """Format an event as a choice label: 'May 2, 4pm — BBQ'.

    Includes minutes only when not :00, e.g. 'May 2, 4:30pm — Standup'.
    """
    summary = event.get("summary", "Untitled Event")
    start_str = event.get("start", {}).get("dateTime", "")

    date_part = ""
    if start_str:
        try:
            dt = datetime.datetime.fromisoformat(start_str)
            dt_eastern = dt.astimezone(EASTERN)
            month = dt_eastern.strftime("%b")
            day = dt_eastern.strftime("%d").lstrip("0")
            minute = dt_eastern.minute
            hour = dt_eastern.hour
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
    ``time_min`` is set to the start of today in US Eastern, so ongoing
    events still appear in the autocomplete dropdown.
    """
    calendar_service = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar_service is None:
        return []

    calendar_id = getattr(calendar_service, "_calendar_id", "default")
    cache_key = (calendar_id,)

    # ── Check cache ──────────────────────────────────────────────────────
    now_ts = time.time()
    cached = _event_cache.get(cache_key)
    if cached is not None:
        cached_ts, cached_events = cached
        if now_ts - cached_ts < _CACHE_TTL:
            return _filter_and_format_choices(cached_events, current)

    # ── Fetch from API ───────────────────────────────────────────────────
    # Start-of-day Eastern — ensures ongoing events still appear
    eastern_now = datetime.datetime.now(EASTERN)
    time_min = eastern_now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = time_min + datetime.timedelta(days=14)

    try:
        events = calendar_service.list_events(
            time_min=time_min.astimezone(datetime.timezone.utc),
            time_max=time_max.astimezone(datetime.timezone.utc),
            max_results=25,
        )
    except RuntimeError:
        logger.warning("Autocomplete list_events failed — returning empty")
        return []

    # ── Store in cache ───────────────────────────────────────────────────
    _event_cache[cache_key] = (now_ts, events)

    return _filter_and_format_choices(events, current)


def _filter_and_format_choices(
    events: list[dict],
    current: str,
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
        label = _format_autocomplete_label(event)
        choices.append(app_commands.Choice(name=label, value=event["id"]))

    return choices[:25]
