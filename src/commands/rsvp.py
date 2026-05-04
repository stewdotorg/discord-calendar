"""/cal rsvp and /cal invite — RSVP and invite others to events."""

import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.delete import delete_event_autocomplete
from src.commands.list_events import cal
from src.utils import format_rsvp_error, resolve_mentions, validate_email

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════════
#  /cal rsvp  and  /cal invite me
# ═══════════════════════════════════════════════════════════════════════════════


async def _add_self_to_event(
    interaction: discord.Interaction,
    event_id: str,
    email: str | None,
    *,
    action: str,
    no_email_msg: str,
) -> None:
    """Resolve the calling user's email and add them as an attendee.

    Shared by ``/cal rsvp`` and ``/cal invite me``.

    Args:
        interaction: The Discord interaction.
        event_id: The Google Calendar event ID.
        email: An explicit email override, or ``None`` to use the stored email.
        action: Label for log messages (e.g. ``"RSVP"``).
        no_email_msg: Error message to show when no email is available.
    """
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
            await interaction.edit_original_response(content=no_email_msg)
            return

    try:
        calendar.add_attendees(event_id, [email])
    except HttpError as exc:
        logger.error("Failed to %s to event %s: %s", action, event_id, exc)
        error_msg = format_rsvp_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    await interaction.edit_original_response(
        content=f"✅ Added as attendee: {email} — "
        "Google Calendar will send an invitation"
    )


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
    """Handle /cal rsvp — add the user as an attendee."""
    await _add_self_to_event(
        interaction,
        event_id,
        email,
        action="RSVP",
        no_email_msg=(
            "❌ No email set. Use `/cal settings email-set` "
            "or pass it inline."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  /cal invite group
# ═══════════════════════════════════════════════════════════════════════════════

invite_group = app_commands.Group(
    name="invite",
    description="Invite attendees to an event",
)
cal.add_command(invite_group)


# ── /cal invite add ─────────────────────────────────────────────────────────


@invite_group.command(
    name="add",
    description="Invite others to an event by email or @mention",
)
@app_commands.describe(
    event_id="Event to invite others to",
    emails="Comma-separated email addresses or @mentions "
           "(e.g. alice@example.com, @bob)",
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def invite_add(
    interaction: discord.Interaction,
    event_id: str,
    emails: str,
) -> None:
    """Handle /cal invite add — parse emails/@mentions and add attendees."""
    if not await _require_calendar(interaction):
        return

    calendar = interaction.client.calendar  # type: ignore[attr-defined]
    settings = interaction.client.settings  # type: ignore[attr-defined]
    await interaction.response.defer()

    raw = [e.strip() for e in emails.split(",") if e.strip()]
    if not raw:
        await interaction.edit_original_response(
            content="❌ No email addresses provided."
        )
        return

    # Resolve @mentions to stored emails, then validate.
    # Mentions are resolved first so that stored emails (already validated
    # during /cal settings email-set) pass through without re-validation.
    resolved, warnings = resolve_mentions(raw, settings)
    for recipient in resolved:
        error = validate_email(recipient)
        if error:
            await interaction.edit_original_response(content=error)
            return

    if not resolved and not warnings:
        await interaction.edit_original_response(
            content="❌ No valid recipients to invite."
        )
        return

    if not resolved:
        # All mentions were unresolvable — show warnings but no invite
        await interaction.edit_original_response(
            content="\n".join(warnings)
        )
        return

    try:
        calendar.add_attendees(event_id, resolved)
    except HttpError as exc:
        logger.error("Failed to invite to event %s: %s", event_id, exc)
        error_msg = format_rsvp_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    count = len(resolved)
    attendee_word = "attendee" if count == 1 else "attendees"

    response = f"✅ Invited {count} {attendee_word}: {', '.join(resolved)}"
    if warnings:
        response += "\n\n" + "\n".join(warnings)

    await interaction.edit_original_response(content=response)


# ── /cal invite me ──────────────────────────────────────────────────────────


@invite_group.command(
    name="me",
    description="Add yourself to an event using your stored email",
)
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
    """Handle /cal invite me — add the calling user as an attendee."""
    await _add_self_to_event(
        interaction,
        event_id,
        email,
        action="invite self",
        no_email_msg=(
            "❌ No email set. Use `/cal settings email-set` "
            "or pass it with "
            "`/cal invite add event_id:... emails:you@example.com`"
        ),
    )
