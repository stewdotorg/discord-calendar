"""/cal invite — invite yourself or others to events with mixed resolution."""

import logging
import re

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.delete import delete_event_autocomplete
from src.commands.list_events import cal
from src.utils import format_invite_error, validate_email

logger = logging.getLogger(__name__)

_MENTION_PATTERN = re.compile(r"^<(?:@!?|@)(\d+)>$")


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


@cal.command(name="invite", description="Invite people to an event")
@app_commands.describe(
    event_id="Event to invite people to",
    people="Comma-separated: 'me', @mentions, or emails (e.g. me, @chaz, alice@example.com)",
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def invite(
    interaction: discord.Interaction,
    event_id: str,
    people: str,
) -> None:
    """Handle invite — mixed-resolution invite to an event.

    The *people* string is comma-separated and accepts:

    * ``me`` — resolved to the caller's stored email.
    * ``<@discord_id>`` — resolved to that user's stored email via SettingsStore.
    * Raw email addresses — validated and used as-is.

    Partial success: valid entries are added as attendees, invalid entries
    produce warnings displayed alongside the success message.
    """
    if not await _require_calendar(interaction):
        return

    calendar = interaction.client.calendar  # type: ignore[attr-defined]
    await interaction.response.defer()

    items = [p.strip() for p in people.split(",") if p.strip()]
    if not items:
        await interaction.edit_original_response(
            content="❌ No people specified."
        )
        return

    resolved: list[str] = []
    warnings: list[str] = []

    for item in items:
        if item.lower() == "me":
            discord_id = str(interaction.user.id)
            email = interaction.client.settings.get(discord_id, "email")
            if email:
                if email not in resolved:
                    resolved.append(email)
            else:
                warnings.append(
                    "⚠️ 'me': no email stored. "
                    "Store one with `/cal settings set email`."
                )
        elif (m := _MENTION_PATTERN.match(item)):
            mentioned_id = m.group(1)
            email = interaction.client.settings.get(mentioned_id, "email")
            if email:
                if email not in resolved:
                    resolved.append(email)
            else:
                warnings.append(
                    f"⚠️ Could not invite {item}: no email stored. "
                    "Ask them to run `/cal settings set email`."
                )
        else:
            error = validate_email(item)
            if error:
                warnings.append(f"⚠️ {item}: {error}")
            elif item not in resolved:
                resolved.append(item)

    if not resolved:
        await interaction.edit_original_response(
            content="❌ No valid recipients.\n" + "\n".join(warnings)
        )
        return

    try:
        calendar.add_attendees(event_id, resolved)
    except HttpError as exc:
        logger.error("Failed to invite to event %s: %s", event_id, exc)
        error_msg = format_invite_error(exc)
        await interaction.edit_original_response(content=error_msg)
        return

    count = len(resolved)
    attendee_word = "attendee" if count == 1 else "attendees"
    lines = [
        f"✅ Invited {count} {attendee_word}: {', '.join(resolved)}"
        " — Google Calendar will send invitation emails"
    ]
    if warnings:
        lines.extend(warnings)

    await interaction.edit_original_response(content="\n".join(lines))
