"""/cal delete command — delete an event from Google Calendar."""

import datetime
import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.utils import EASTERN, format_delete_error

logger = logging.getLogger(__name__)

# Reference the cal group defined in list_events to register on it
from src.commands.list_events import cal  # noqa: E402

TRUNCATE_AT = 100


async def delete_event_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete callback — queries Google Calendar for upcoming events
    and filters by the user's typed substring."""
    calendar_service = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar_service is None:
        return []

    # Look ahead 14 days for autocomplete suggestions
    now = datetime.datetime.now(datetime.timezone.utc)
    time_max = now + datetime.timedelta(days=14)

    try:
        events = calendar_service.list_events(
            time_min=now,
            time_max=time_max,
            max_results=25,
        )
    except RuntimeError:
        logger.warning("Autocomplete list_events failed — returning empty")
        return []

    query = current.strip().lower()

    choices: list[app_commands.Choice[str]] = []
    for event in events:
        summary = event.get("summary", "Untitled Event")
        if query and query not in summary.lower():
            continue
        truncated = _truncate_for_autocomplete(summary)
        choices.append(app_commands.Choice(name=truncated, value=event["id"]))

    # Discord limits autocomplete to 25 choices
    return choices[:25]


def _truncate_for_autocomplete(title: str) -> str:
    """Truncate an event title for display in the autocomplete dropdown.

    Discord choice names are limited to 100 characters.
    """
    if len(title) <= TRUNCATE_AT:
        return title
    return title[: TRUNCATE_AT - 1] + "…"


@cal.command(name="delete", description="Delete a Google Calendar event")
@app_commands.describe(event_id="Event to delete")
@app_commands.autocomplete(event_id=delete_event_autocomplete)
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

    # Format event date for the confirmation message
    summary = event_info["summary"]
    start_str = event_info["start"]
    date_display = ""
    if start_str:
        try:
            dt = datetime.datetime.fromisoformat(start_str)
            dt_eastern = dt.astimezone(EASTERN)
            month = dt_eastern.strftime("%B")
            day = dt_eastern.strftime("%d").lstrip("0")
            year = dt_eastern.strftime("%Y")
            time_str = dt_eastern.strftime("%I:%M %p").lstrip("0")
            date_display = f" on {month} {day}, {year} at {time_str} ET"
        except (ValueError, OverflowError):
            pass  # Malformed date string — omit date from confirmation

    await interaction.response.send_message(
        f"🗑️ **{summary}** deleted{date_display}.",
        ephemeral=False,
    )
