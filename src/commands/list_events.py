"""/cal today command — list today's events from Google Calendar."""

import logging

import discord
from discord import app_commands

from src.utils import EASTERN, format_events_embed, get_today_eastern_range

logger = logging.getLogger(__name__)

cal = app_commands.Group(name="cal", description="Calendar commands")


@cal.command(name="today", description="List today's events")
async def today(interaction: discord.Interaction) -> None:
    """List all events scheduled for today in the shared calendar."""
    calendar_service = interaction.client.calendar

    if calendar_service is None:
        await interaction.response.send_message(
            "Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return

    time_min, time_max = get_today_eastern_range()

    try:
        events = calendar_service.list_events(time_min=time_min, time_max=time_max)
    except RuntimeError as exc:
        logger.error("Failed to list today's events: %s", exc)
        await interaction.response.send_message(
            "Failed to fetch today's events. Please try again later.",
            ephemeral=True,
        )
        return

    # Build date title from US Eastern date
    now_eastern = time_min.astimezone(EASTERN)
    date_title = now_eastern.strftime("%B %d, %Y")

    embed = format_events_embed(events, date_title=date_title)
    await interaction.response.send_message(embed=embed)
