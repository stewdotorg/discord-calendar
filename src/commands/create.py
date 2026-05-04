"""create — create a Google Calendar event from a Discord slash command."""

import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.list_events import cal
from src.utils import (
    format_create_error,
    format_datetime_eastern,
    format_invite_error,
    get_user_timezone,
    parse_minutes,
    parse_when,
    resolve_mentions,
    validate_email,
)

logger = logging.getLogger(__name__)


@cal.command(name="create", description="Create a Google Calendar event")
@app_commands.describe(
    title="Event title",
    when='Start time in US Eastern, e.g. "May 1 3pm", "5/1 15:00", '
         '"tomorrow 2pm", "2026-05-01 14:00"',
    duration="Duration in minutes (default: 60)",
    description="Optional event description",
    invite="Comma-separated list of @mentions and/or email addresses to invite",
)
async def create(
    interaction: discord.Interaction,
    title: str,
    when: str,
    duration: int = 60,
    description: str | None = None,
    invite: str | None = None,
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

    # ── Resolve @mentions and validate raw emails ──────────────────────────
    invite_emails: list[str] = []
    invite_warnings: list[str] = []

    if invite:
        settings = interaction.client.settings  # type: ignore[attr-defined]
        items = [item.strip() for item in invite.split(",") if item.strip()]
        invite_emails, invite_warnings = resolve_mentions(items, settings)
        # Validate raw emails that were not @mentions
        validated_emails: list[str] = []
        for email in invite_emails:
            error = validate_email(email)
            if error:
                invite_warnings.append(error)
            else:
                validated_emails.append(email)
        invite_emails = validated_emails

    user_tz = get_user_timezone(interaction)

    try:
        start = parse_when(when, tz=user_tz)
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

    # ── Add attendees if invite emails were resolved ───────────────────────
    if invite_emails:
        try:
            calendar.add_attendees(result["id"], invite_emails)
        except HttpError as exc:
            logger.error("Failed to add attendees: %s", exc)
            error_msg = format_invite_error(exc)
            invite_warnings.append(error_msg)

    # Auto-apply user's default reminders if configured
    default_reminders = interaction.client.settings.get(  # type: ignore[attr-defined]
        creator_discord_id, "default_reminders"
    )
    if default_reminders:
        try:
            minutes_list = parse_minutes(default_reminders)
            calendar.add_reminders(result["id"], minutes_list)
        except (ValueError, HttpError) as exc:
            logger.warning(
                "Failed to apply default reminders for user %s: %s",
                creator_discord_id, exc,
            )

    # Display confirmation in user's timezone
    start_fmt = format_datetime_eastern(start, tz=user_tz)

    response = (
        f"✅ **Event created!**\n"
        f"**{title}**\n"
        f"📅 {start_fmt} ET  "
        f"({duration} min)\n"
        f"[Open in Google Calendar]({result['htmlLink']})"
    )
    if description:
        response += f"\n📝 {description}"

    if invite_warnings:
        response += "\n" + "\n".join(invite_warnings)

    await interaction.edit_original_response(content=response)
