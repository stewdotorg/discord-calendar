"""create — create a Google Calendar event from a Discord slash command."""

import datetime
import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.list_events import cal
from src.utils import format_create_error

logger = logging.getLogger(__name__)


@cal.command(name="create", description="Create a Google Calendar event")
@app_commands.describe(
    title="Event title",
    date="Date (YYYY-MM-DD)",
    time="Start time (HH:MM, 24-hour format, UTC)",
    duration="Duration in minutes (default: 60)",
    description="Optional event description",
)
async def create(
    interaction: discord.Interaction,
    title: str,
    date: str,
    time: str,
    duration: int = 60,
    description: str | None = None,
) -> None:
    """Handle create — parse arguments, call CalendarService, respond."""
    calendar = interaction.client.calendar  # type: ignore[attr-defined]  # set in DiscalClient.setup_hook

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Set GOOGLE_SERVICE_ACCOUNT_FILE "
            "and GOOGLE_CALENDAR_ID in `.env`.",
            ephemeral=True,
        )
        return

    try:
        start = datetime.datetime.strptime(
            f"{date} {time}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid date or time format. Use `YYYY-MM-DD` for date "
            "and `HH:MM` for time (24-hour, UTC).",
            ephemeral=True,
        )
        return

    creator_discord_id = str(interaction.user.id)

    try:
        result = calendar.create_event(
            title=title,
            start=start,
            duration_minutes=duration,
            description=description,
            creator_discord_id=creator_discord_id,
        )
    except HttpError as exc:
        logger.error("Failed to create event: %s", exc)
        error_msg = format_create_error(exc)
        await interaction.response.send_message(error_msg, ephemeral=True)
        return

    end = start + datetime.timedelta(minutes=duration)
    response = (
        f"✅ **Event created!**\n"
        f"**{title}**\n"
        f"📅 {start.strftime('%Y-%m-%d')}  "
        f"⏰ {start.strftime('%H:%M')}–{end.strftime('%H:%M')} UTC  "
        f"({duration} min)\n"
        f"[Open in Google Calendar]({result['htmlLink']})"
    )
    if description:
        response += f"\n📝 {description}"

    await interaction.response.send_message(response, ephemeral=False)
