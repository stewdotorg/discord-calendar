"""/cal rsvp and /cal invite — RSVP and invite others to events."""

import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.delete import delete_event_autocomplete
from src.commands.list_events import cal
from src.utils import format_rsvp_error, validate_email

logger = logging.getLogger(__name__)


@cal.command(name="rsvp", description="RSVP to an event using your stored email")
@app_commands.describe(
    event_id="Event to RSVP to",
    email="Email address (optional — uses stored email if omitted)",
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def rsvp(
    interaction: discord.Interaction,
    event_id: str,
    email: str | None = None,
) -> None:
    """Handle RSVP — add user (or specified email) as an attendee."""
    calendar = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    if email is not None:
        error = validate_email(email)
        if error:
            await interaction.edit_original_response(content=error)
            return
    else:
        discord_id = str(interaction.user.id)
        email = interaction.client.settings.get(discord_id, "email")
        if not email:
            await interaction.edit_original_response(
                content=(
                    "❌ No email set. Store one with `/cal email set` "
                    "or pass it inline."
                )
            )
            return

    try:
        calendar.add_attendees(event_id, [email])
    except HttpError as exc:
        logger.error("Failed to RSVP to event %s: %s", event_id, exc)
        error_msg = format_rsvp_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    await interaction.edit_original_response(
        content=f"✅ Added as attendee: {email} — "
        "Google Calendar will send an invitation"
    )


@cal.command(name="invite", description="Invite others to an event by email")
@app_commands.describe(
    event_id="Event to invite others to",
    emails="Comma-separated email addresses (e.g. alice@example.com, bob@example.com)",
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def invite(
    interaction: discord.Interaction,
    event_id: str,
    emails: str,
) -> None:
    """Handle invite — add comma-separated emails as attendees."""
    calendar = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    parsed = [e.strip() for e in emails.split(",") if e.strip()]
    if not parsed:
        await interaction.edit_original_response(
            content="❌ No email addresses provided."
        )
        return

    for addr in parsed:
        error = validate_email(addr)
        if error:
            await interaction.edit_original_response(content=error)
            return

    try:
        calendar.add_attendees(event_id, parsed)
    except HttpError as exc:
        logger.error("Failed to invite to event %s: %s", event_id, exc)
        error_msg = format_rsvp_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    attendee_word = "attendee" if len(parsed) == 1 else "attendees"
    await interaction.edit_original_response(
        content=f"✅ Invited {len(parsed)} {attendee_word}: {', '.join(parsed)}"
    )
