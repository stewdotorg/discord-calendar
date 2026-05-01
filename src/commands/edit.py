"""/cal edit command — edit a Google Calendar event."""

import datetime
import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.delete import delete_event_autocomplete
from src.commands.list_events import cal
from src.utils import format_datetime_eastern, format_edit_error, parse_when

logger = logging.getLogger(__name__)


@cal.command(name="edit", description="Edit a Google Calendar event")
@app_commands.describe(
    event_id="Event to edit",
    title="New event title",
    when='New start time in US Eastern, e.g. "May 1 3pm", "5/1 15:00"',
    duration="New duration in minutes",
    description="New event description",
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def edit(
    interaction: discord.Interaction,
    event_id: str,
    title: str | None = None,
    when: str | None = None,
    duration: int | None = None,
    description: str | None = None,
) -> None:
    """Handle edit — fetch current event, apply changes, respond with confirmation."""
    calendar = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return

    # Defer — API calls may exceed Discord's 3-second interaction timeout.
    await interaction.response.defer()

    # Fetch the current event first
    try:
        current = calendar.get_event(event_id)
    except HttpError as exc:
        logger.error("Failed to get event %s: %s", event_id, exc)
        error_msg = format_edit_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    has_changes = any(
        p is not None for p in [title, when, duration, description]
    )

    if not has_changes:
        # Show current event details with "No changes specified"
        await _respond_no_changes(interaction, current)
        return

    # Parse when and build patch body
    patch_body = {}

    if title is not None:
        patch_body["summary"] = title

    if description is not None:
        patch_body["description"] = description

    if when is not None or duration is not None:
        try:
            new_start, new_end = _compute_start_end(
                current, when, duration
            )
        except ValueError as exc:
            await interaction.edit_original_response(
                content=f"❌ Cannot parse '{when}': {exc}"
            )
            return
        patch_body["start"] = {
            "dateTime": new_start.isoformat(),
            "timeZone": "UTC",
        }
        patch_body["end"] = {
            "dateTime": new_end.isoformat(),
            "timeZone": "UTC",
        }

    try:
        result = calendar.update_event(event_id, **patch_body)
    except HttpError as exc:
        logger.error("Failed to update event %s: %s", event_id, exc)
        error_msg = format_edit_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    # Build confirmation message
    response = _format_confirmation(current, patch_body, result["htmlLink"])
    await interaction.edit_original_response(content=response)


def _compute_start_end(
    current: dict,
    when: str | None,
    duration: int | None,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Compute new start and end datetimes from the current event and user input.

    Args:
        current: The current event dict (must have start.dateTime and end.dateTime).
        when: Optional new start time string (parsed via parse_when).
        duration: Optional new duration in minutes.

    Returns:
        A tuple of (new_start, new_end) as timezone-aware UTC datetimes.

    Raises:
        ValueError: If when cannot be parsed.
    """
    current_start_str = current["start"]["dateTime"]
    current_end_str = current["end"]["dateTime"]
    current_start = datetime.datetime.fromisoformat(current_start_str)
    current_end = datetime.datetime.fromisoformat(current_end_str)

    if when is not None:
        new_start = parse_when(when)
    else:
        new_start = current_start

    if duration is not None:
        new_end = new_start + datetime.timedelta(minutes=duration)
    elif when is not None:
        existing_minutes = (current_end - current_start).total_seconds() / 60
        new_end = new_start + datetime.timedelta(minutes=int(existing_minutes))
    else:
        new_end = current_end

    return new_start, new_end


async def _respond_no_changes(
    interaction: discord.Interaction,
    current: dict,
) -> None:
    """Respond with current event details and a 'No changes specified' message."""
    summary = current.get("summary", "Untitled Event")
    start_str = current.get("start", {}).get("dateTime", "")
    end_str = current.get("end", {}).get("dateTime", "")
    description = current.get("description", "")
    html_link = current.get("htmlLink", "")

    time_line = ""
    if start_str and end_str:
        try:
            start_dt = datetime.datetime.fromisoformat(start_str)
            end_dt = datetime.datetime.fromisoformat(end_str)
            duration_min = int(
                (end_dt - start_dt).total_seconds() / 60
            )
            start_fmt = format_datetime_eastern(start_dt)
            time_line = f"📅 {start_fmt} ET  ({duration_min} min)"
        except (ValueError, OverflowError):
            pass

    response = (
        f"ℹ️ **No changes specified.**\n\n"
        f"**{summary}**\n"
    )
    if time_line:
        response += f"{time_line}\n"
    if html_link:
        response += f"[Open in Google Calendar]({html_link})\n"
    if description:
        response += f"\n📝 {description}"

    await interaction.edit_original_response(content=response)


def _format_confirmation(
    current: dict,
    patch_body: dict,
    html_link: str,
) -> str:
    """Build the confirmation message showing updated event details.

    Args:
        current: The current (pre-update) event dict.
        patch_body: The changes that were applied.
        html_link: The htmlLink from the updated event.

    Returns:
        A formatted confirmation string.
    """
    new_title = patch_body.get("summary", current.get("summary", "Untitled Event"))
    old_title = current.get("summary", "Untitled Event")

    new_description = patch_body.get(
        "description", current.get("description", "")
    )

    if "start" in patch_body:
        start_dt = datetime.datetime.fromisoformat(
            patch_body["start"]["dateTime"]
        )
        end_dt = datetime.datetime.fromisoformat(
            patch_body["end"]["dateTime"]
        )
    else:
        start_str = current.get("start", {}).get("dateTime", "")
        end_str = current.get("end", {}).get("dateTime", "")
        start_dt = datetime.datetime.fromisoformat(start_str)
        end_dt = datetime.datetime.fromisoformat(end_str)

    duration_min = int((end_dt - start_dt).total_seconds() / 60)
    start_fmt = format_datetime_eastern(start_dt)

    response = "✅ **Event updated!**\n"
    if new_title != old_title:
        response += f"**{old_title}** → **{new_title}**\n"
    else:
        response += f"**{new_title}**\n"

    response += (
        f"📅 {start_fmt} ET  ({duration_min} min)\n"
        f"[Open in Google Calendar]({html_link})"
    )

    if new_description:
        response += f"\n📝 {new_description}"

    return response
