"""/cal invite group — invite yourself or others to events."""

import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.delete import delete_event_autocomplete
from src.commands.list_events import cal
from src.utils import format_rsvp_error, validate_email

logger = logging.getLogger(__name__)

invite_group = app_commands.Group(
    name="invite",
    description="Invite yourself or others to an event",
    parent=cal,
)


async def _require_calendar(interaction: discord.Interaction) -> bool:
    """Check that the calendar service is configured on the client.

    Sends an ephemeral error message and returns False if the calendar is
    not configured.  Returns True otherwise so the caller can proceed.
    """
    if interaction.client.calendar is None:  # type: ignore[attr-defined]
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return False
    return True


@invite_group.command(name="me", description="Add yourself as an attendee")
@app_commands.describe(
    event_id="Event to add yourself to",
    email="Email address (optional — uses stored email if omitted)",
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def invite_me(
    interaction: discord.Interaction,
    event_id: str,
    email: str | None = None,
) -> None:
    """Handle invite me — add the calling user (or specified email) as an attendee."""
    if not await _require_calendar(interaction):
        return

    calendar = interaction.client.calendar  # type: ignore[attr-defined]
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
                    "❌ No email set. Store one with `/cal settings email-set` "
                    "or pass it inline."
                )
            )
            return

    try:
        calendar.add_attendees(event_id, [email])
    except HttpError as exc:
        logger.error("Failed to add attendee to event %s: %s", event_id, exc)
        error_msg = format_rsvp_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    await interaction.edit_original_response(
        content=f"✅ Added as attendee: {email} — "
        "Google Calendar will send an invitation"
    )


@invite_group.command(name="by-email", description="Invite others to an event by email")
@app_commands.describe(
    event_id="Event to invite others to",
    emails="Comma-separated email addresses (e.g. alice@example.com, bob@example.com)",
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def invite_by_email(
    interaction: discord.Interaction,
    event_id: str,
    emails: str,
) -> None:
    """Handle invite by-email — add comma-separated emails as attendees."""
    if not await _require_calendar(interaction):
        return

    calendar = interaction.client.calendar  # type: ignore[attr-defined]
    await interaction.response.defer()

    recipients = [e.strip() for e in emails.split(",") if e.strip()]
    if not recipients:
        await interaction.edit_original_response(
            content="❌ No email addresses provided."
        )
        return

    for recipient in recipients:
        error = validate_email(recipient)
        if error:
            await interaction.edit_original_response(content=error)
            return

    try:
        calendar.add_attendees(event_id, recipients)
    except HttpError as exc:
        logger.error("Failed to invite to event %s: %s", event_id, exc)
        error_msg = format_rsvp_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    count = len(recipients)
    attendee_word = "attendee" if count == 1 else "attendees"
    await interaction.edit_original_response(
        content=f"✅ Invited {count} {attendee_word}: {', '.join(recipients)}"
    )

