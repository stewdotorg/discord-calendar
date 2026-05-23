"""/cal invite — invite yourself or others to events with mixed resolution.

Also provides the RSVP-button flow (RsvpView, EmailModal) attached to event
creation posts so users can self-invite with a single click.
"""

import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.autocomplete import event_autocomplete
from src.commands.list_events import cal
from src.utils import _MENTION_PATTERN, format_invite_error, validate_email

logger = logging.getLogger(__name__)


# ── RSVP button (attached to /cal create posts) ───────────────────────────


class EmailModal(discord.ui.Modal, title="Enter your email"):
    """Modal for collecting a user's email when they click RSVP without one stored."""

    email_input = discord.ui.TextInput(
        label="Email address",
        placeholder="you@example.com",
        required=True,
        min_length=5,
        max_length=254,
    )

    def __init__(self, event_id: str) -> None:
        super().__init__()
        self._event_id = event_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Validate email, save to settings, and add as attendee."""
        email = self.email_input.value.strip()
        error = validate_email(email)
        if error:
            await interaction.response.send_message(
                "❌ Invalid email. Please enter a valid email like you@example.com.",
                ephemeral=True,
            )
            return

        discord_id = str(interaction.user.id)
        interaction.client.settings.set(discord_id, "email", email)  # type: ignore[attr-defined]

        calendar = interaction.client.calendar  # type: ignore[attr-defined]
        try:
            event = calendar.get_event(self._event_id)
            event_title = event.get("summary", "the event")
            calendar.add_attendees(self._event_id, [email])
        except HttpError:
            await interaction.response.send_message(
                "❌ Could not add you — please try again.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Email saved! You have been added to {event_title}!",
            ephemeral=True,
        )


async def _handle_rsvp_interaction(
    interaction: discord.Interaction, event_id: str
) -> None:
    """Handle an RSVP button click.

    If the user has an email on file, add them as an attendee directly.
    If not, open ``EmailModal`` to collect their email first.
    """
    settings = interaction.client.settings  # type: ignore[attr-defined]
    calendar = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured.", ephemeral=True
        )
        return

    discord_id = str(interaction.user.id)
    email = settings.get(discord_id, "email")

    if email:
        try:
            event = calendar.get_event(event_id)
            attendees = event.get("attendees", [])
            if any(a.get("email", "").lower() == email.lower() for a in attendees):
                await interaction.response.send_message(
                    "You are already on the list for this event.",
                    ephemeral=True,
                )
                return

            calendar.add_attendees(event_id, [email])
            event_title = event.get("summary", "the event")
            await interaction.response.send_message(
                f"✅ You have been added to {event_title}!",
                ephemeral=True,
            )
        except HttpError:
            logger.error("RSVP API error for user %s, event %s", discord_id, event_id)
            await interaction.response.send_message(
                "❌ Could not add you — please try again.",
                ephemeral=True,
            )
    else:
        modal = EmailModal(event_id=event_id)
        await interaction.response.send_modal(modal)


class RsvpView(discord.ui.View):
    """Persistent View with an RSVP button for event posts.

    The event ID is encoded in the button's ``custom_id`` (``rsvp:event_id``)
    so the handler can recover it after bot restarts.
    """

    def __init__(self, event_id: str) -> None:
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="📅 RSVP",
            style=discord.ButtonStyle.primary,
            custom_id=f"rsvp:{event_id}",
        )
        button.callback = self._rsvp_callback
        self.add_item(button)

    async def _rsvp_callback(self, interaction: discord.Interaction) -> None:
        """Extract event_id from custom_id and delegate to shared handler."""
        custom_id = interaction.data.get("custom_id", "")  # type: ignore[union-attr]
        event_id = custom_id[5:]  # strip "rsvp:"
        await _handle_rsvp_interaction(interaction, event_id)


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
@app_commands.rename(event_id="event")
@app_commands.describe(
    event_id="Event to invite people to",
    people="Comma-separated: 'me', @mentions, or emails (e.g. me, @chaz, alice@example.com)",
)
@app_commands.autocomplete(event_id=event_autocomplete)
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
        f" — Google Calendar will send invitation emails"
    ]
    if warnings:
        lines.extend(warnings)

    await interaction.edit_original_response(content="\n".join(lines))
