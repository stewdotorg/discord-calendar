"""create — create a Google Calendar event from a Discord slash command."""

import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.list_events import cal
from src.utils import format_create_error, format_datetime_eastern, parse_when

logger = logging.getLogger(__name__)


@cal.command(name="create", description="Create a Google Calendar event")
@app_commands.describe(
    title="Event title",
    when='Start time in US Eastern, e.g. "May 1 3pm", "5/1 15:00", '
         '"tomorrow 2pm", "2026-05-01 14:00"',
    duration="Duration in minutes (default: 60)",
    description="Optional event description",
)
async def create(
    interaction: discord.Interaction,
    title: str,
    when: str,
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

    # Defer response — dateparser and Google Calendar API calls may exceed
    # Discord's 3-second interaction timeout.
    await interaction.response.defer()

    try:
        start = parse_when(when)
    except ValueError as exc:
        await interaction.edit_original_response(
            content=f"❌ Cannot parse '{when}': {exc}"
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
        await interaction.edit_original_response(content=error_msg)
        return

    # Display confirmation in US Eastern
    start_fmt = format_datetime_eastern(start)

    response = (
        f"✅ **Event created!**\n"
        f"**{title}**\n"
        f"📅 {start_fmt} ET  "
        f"({duration} min)\n"
        f"[Open in Google Calendar]({result['htmlLink']})"
    )
    if description:
        response += f"\n📝 {description}"

    await interaction.edit_original_response(content=response)
