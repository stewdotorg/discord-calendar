"""/cal today, /cal week, /cal list — list events from Google Calendar."""

import datetime
import logging
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from src.utils import (
    EASTERN,
    format_events_embed,
    get_today_eastern_range,
    get_user_timezone,
    parse_date_eastern,
)

logger = logging.getLogger(__name__)

cal = app_commands.Group(name="cal", description="Calendar commands")

_NOT_CONFIGURED_MSG = (
    "Calendar is not configured. Ask an admin to set "
    "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID."
)


def _fetch_events_embed(
    interaction: discord.Interaction,
    time_min: datetime.datetime,
    time_max: datetime.datetime,
    date_title: str,
    q: str | None = None,
    tz: ZoneInfo = EASTERN,
) -> discord.Embed:
    """Fetch events and build a formatted embed.

    Args:
        interaction: The Discord interaction (used to access the calendar service).
        time_min: Start of the time range (timezone-aware UTC datetime).
        time_max: End of the time range (timezone-aware UTC datetime).
        date_title: Human-readable date title for the embed.
        q: Optional search keyword.
        tz: The timezone to display event times in (default US Eastern).

    Returns:
        A discord.Embed with the formatted event list.

    Raises:
        _CalendarNotConfigured: If the calendar service is None.
        _FetchFailed: If the Google Calendar API call fails.
    """
    calendar_service = interaction.client.calendar

    if calendar_service is None:
        raise _CalendarNotConfigured()

    try:
        events = calendar_service.list_events(
            time_min=time_min, time_max=time_max, q=q
        )
    except RuntimeError as exc:
        logger.error("Failed to list events: %s", exc)
        raise _FetchFailed() from exc

    embed = format_events_embed(events, date_title=date_title, tz=tz)
    return embed


class _CalendarNotConfigured(Exception):
    """Raised when the calendar service is None."""


class _FetchFailed(Exception):
    """Raised when list_events fails."""


@cal.command(name="today", description="List today's events")
async def today(interaction: discord.Interaction) -> None:
    """List all events scheduled for today in the shared calendar."""
    try:
        user_tz = get_user_timezone(interaction)
        time_min, time_max = get_today_eastern_range(tz=user_tz)
        now_local = time_min.astimezone(user_tz)
        date_title = now_local.strftime("%B %d, %Y")
        embed = _fetch_events_embed(
            interaction, time_min, time_max, date_title, tz=user_tz
        )
        await interaction.response.send_message(embed=embed)
    except _CalendarNotConfigured:
        await interaction.response.send_message(
            _NOT_CONFIGURED_MSG, ephemeral=True
        )
    except _FetchFailed:
        await interaction.response.send_message(
            "Failed to fetch today's events. Please try again later.",
            ephemeral=True,
        )


@cal.command(name="week", description="List events for the next 7 days")
async def week(interaction: discord.Interaction) -> None:
    """List all events from today through the next 7 days."""
    try:
        user_tz = get_user_timezone(interaction)
        time_min, _today_end = get_today_eastern_range(tz=user_tz)
        time_max = time_min + datetime.timedelta(days=7)

        start_local = time_min.astimezone(user_tz)
        end_local = time_max.astimezone(user_tz)
        date_title = (
            f"{start_local.strftime('%B %d')}–{end_local.strftime('%B %d, %Y')}"
        )

        embed = _fetch_events_embed(
            interaction, time_min, time_max, date_title, tz=user_tz
        )
        await interaction.response.send_message(embed=embed)
    except _CalendarNotConfigured:
        await interaction.response.send_message(
            _NOT_CONFIGURED_MSG, ephemeral=True
        )
    except _FetchFailed:
        await interaction.response.send_message(
            "Failed to fetch events. Please try again later.",
            ephemeral=True,
        )


@cal.command(name="list", description="List events in a date range")
@app_commands.rename(from_="from")
@app_commands.describe(
    from_="Start date (YYYY-MM-DD)",
    to="End date (YYYY-MM-DD)",
    search="Optional keyword to search event titles and descriptions",
)
async def list_events(
    interaction: discord.Interaction,
    from_: str,
    to: str,
    search: str | None = None,
) -> None:
    """List events in a custom date range.

    Dates are interpreted in the user's timezone at midnight.
    """
    try:
        user_tz = get_user_timezone(interaction)
        time_min = parse_date_eastern(from_, tz=user_tz)
        time_max = parse_date_eastern(to, tz=user_tz)
    except ValueError as exc:
        await interaction.response.send_message(
            f"❌ Invalid date: {exc}", ephemeral=True
        )
        return

    try:
        dt_min_local = time_min.astimezone(user_tz)
        dt_max_local = time_max.astimezone(user_tz)
        date_title = (
            f"{dt_min_local.strftime('%B %d')}–"
            f"{dt_max_local.strftime('%B %d, %Y')}"
        )
        embed = _fetch_events_embed(
            interaction, time_min, time_max, date_title, q=search, tz=user_tz
        )
        await interaction.response.send_message(embed=embed)
    except _CalendarNotConfigured:
        await interaction.response.send_message(
            _NOT_CONFIGURED_MSG, ephemeral=True
        )
    except _FetchFailed:
        await interaction.response.send_message(
            "Failed to fetch events. Please try again later.",
            ephemeral=True,
        )
