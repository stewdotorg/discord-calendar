"""/cal delete command — delete an event from Google Calendar."""

import datetime
import logging
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.autocomplete import event_autocomplete
from src.utils import (
    DEFAULT_TIMEZONE,
    format_datetime_eastern,
    format_delete_error,
)

logger = logging.getLogger(__name__)

# Reference the cal group defined in list_events to register on it
from src.commands.list_events import cal  # noqa: E402


@cal.command(name="delete", description="Delete a Google Calendar event")
@app_commands.rename(event_id="event")
@app_commands.describe(event_id="Event to delete")
@app_commands.autocomplete(event_id=event_autocomplete)
async def delete(interaction: discord.Interaction, event_id: str) -> None:
    """Handle delete — call CalendarService, respond with confirmation."""
    calendar_service = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar_service is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return

    try:
        event_info = calendar_service.delete_event(event_id)
    except HttpError as exc:
        logger.error("Failed to delete event %s: %s", event_id, exc)
        error_msg = format_delete_error(exc)
        await interaction.response.send_message(error_msg, ephemeral=True)
        return

    # ── Resolve per-user timezone for confirmation display ───────────────
    user_id = str(interaction.user.id)
    settings = interaction.client.settings  # type: ignore[attr-defined]
    tz_str = settings.get(user_id, "timezone")
    try:
        user_tz = ZoneInfo(tz_str) if tz_str else DEFAULT_TIMEZONE
    except Exception:
        user_tz = DEFAULT_TIMEZONE

    # Format event date for the confirmation message
    summary = event_info["summary"]
    start_str = event_info["start"]
    date_display = ""
    if start_str:
        try:
            dt = datetime.datetime.fromisoformat(start_str)
            date_display = f" on {format_datetime_eastern(dt, tz=user_tz)} ET"
        except (ValueError, OverflowError):
            pass  # Malformed date string — omit date from confirmation

    await interaction.response.send_message(
        f"🗑️ **{summary}** deleted{date_display}.",
        ephemeral=False,
    )
