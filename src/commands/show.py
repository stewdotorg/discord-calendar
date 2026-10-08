"""/cal show command — re-advertise an existing event.

Renders the same details block /cal create posts, using the event's current
state, with a "Post to channel" button that posts it with the RSVP button.
Useful for resurfacing an event after a lot of scrollback.
"""

import datetime
import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.autocomplete import event_autocomplete
from src.commands.list_events import cal
from src.commands.rsvp import RsvpView
from src.utils import format_event_details, get_user_timezone
from src.views import PostToChannelView

logger = logging.getLogger(__name__)


@cal.command(name="show", description="Show an event, with an option to post it to the channel")
@app_commands.rename(event_id="event")
@app_commands.describe(event_id="Event to show")
@app_commands.autocomplete(event_id=event_autocomplete)
async def show(interaction: discord.Interaction, event_id: str) -> None:
    """Handle show — fetch the event's current state and render it."""
    calendar = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
            view=PostToChannelView(),
        )
        return

    # Defer — the API call may exceed Discord's 3-second interaction timeout.
    await interaction.response.defer(ephemeral=True)

    try:
        event = calendar.get_event(event_id)
    except HttpError as exc:
        logger.error("Failed to get event %s: %s", event_id, exc)
        status = exc.resp.status if exc.resp else 0
        if status == 404:
            msg = "❌ Event not found — it may have been deleted."
        else:
            msg = f"❌ Failed to fetch event. ({status})"
        await interaction.edit_original_response(content=msg, view=PostToChannelView())
        return

    start_raw = event.get("start", {})
    end_raw = event.get("end", {})
    if "dateTime" in start_raw:
        start = datetime.datetime.fromisoformat(start_raw["dateTime"])
        end = datetime.datetime.fromisoformat(end_raw["dateTime"])
        duration_min = int((end - start).total_seconds() / 60)
    else:
        start = datetime.date.fromisoformat(start_raw["date"])
        duration_min = None

    details = format_event_details(
        event.get("summary", "Untitled Event"),
        start,
        event.get("htmlLink", ""),
        duration_min,
        event.get("description"),
        tz=get_user_timezone(interaction),
    )

    await interaction.edit_original_response(
        content=details,
        view=PostToChannelView(
            posted_view=RsvpView(event_id=event_id),
            post_content=details,
        ),
    )
