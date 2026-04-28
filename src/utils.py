"""Utility functions — embed formatting, timezone conversion, autocomplete helpers."""

import datetime
from zoneinfo import ZoneInfo

import discord

EASTERN = ZoneInfo("America/New_York")


def get_today_eastern_range() -> tuple[datetime.datetime, datetime.datetime]:
    """Return (start_of_today_utc, end_of_today_utc) covering today in US Eastern.

    Returns timezone-aware UTC datetimes.
    """
    now_eastern = datetime.datetime.now(EASTERN)
    start_eastern = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
    end_eastern = start_eastern + datetime.timedelta(days=1)

    start_utc = start_eastern.astimezone(datetime.timezone.utc)
    end_utc = end_eastern.astimezone(datetime.timezone.utc)

    return start_utc, end_utc


def _format_time_eastern(date_time_str: str) -> str:
    """Convert an ISO 8601 datetime string to US Eastern 12-hour time.

    Args:
        date_time_str: An ISO 8601 string like '2026-04-28T10:00:00-04:00'.

    Returns:
        A string like '10:00 AM'.
    """
    dt = datetime.datetime.fromisoformat(date_time_str)
    dt_eastern = dt.astimezone(EASTERN)
    return dt_eastern.strftime("%-I:%M %p")


def _format_duration(start_str: str, end_str: str) -> str:
    """Compute a human-readable duration between two ISO 8601 datetime strings.

    Returns a string like '1h 30m' or '45m'.
    """
    start_dt = datetime.datetime.fromisoformat(start_str)
    end_dt = datetime.datetime.fromisoformat(end_str)
    delta = end_dt - start_dt

    total_minutes = int(delta.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{minutes}m"


def format_events_embed(
    events: list[dict], date_title: str | None = None
) -> discord.Embed:
    """Build a Discord embed that lists calendar events.

    Args:
        events: List of Google Calendar event dicts.
        date_title: Human-readable date for the embed title
                    (e.g. 'April 28, 2026'). If None, uses 'Today'.

    Returns:
        A discord.Embed with events formatted as fields.
    """
    if date_title is None:
        date_title = "Today"

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

        time_str = _format_time_eastern(start_str) if start_str else "?"
        duration_str = _format_duration(start_str, end_str) if start_str and end_str else "?"

        value_lines = [f"**Start:** {time_str} ET", f"**Duration:** {duration_str}"]
        if html_link:
            value_lines.append(f"[Open in Google Calendar]({html_link})")

        embed.add_field(
            name=summary,
            value="\n".join(value_lines),
            inline=False,
        )

    return embed
