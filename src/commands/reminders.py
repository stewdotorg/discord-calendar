"""/cal reminders — set and show event reminders, plus default reminder prefs."""

import logging

import discord
from discord import app_commands
from googleapiclient.errors import HttpError

from src.commands.delete import delete_event_autocomplete
from src.commands.list_events import cal
from src.utils import format_edit_error, parse_minutes

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────


def _format_reminders_list(minutes: list[int]) -> str:
    """Format a list of reminder minutes for display.

    Args:
        minutes: List of minutes-before values (already sorted).

    Returns:
        A human-readable string like '10 min, 30 min before'.
    """
    if not minutes:
        return ""
    sorted_minutes = sorted(minutes)
    parts = [f"{m} min" for m in sorted_minutes]
    if len(parts) == 1:
        return f"{parts[0]} before"
    return f"{', '.join(parts)} before"


# ── /cal reminders ───────────────────────────────────────────────────────────


reminders_group = app_commands.Group(
    name="reminders",
    description="Manage event reminders",
    parent=cal,
)


@reminders_group.command(
    name="set", description="Set reminders on a Google Calendar event"
)
@app_commands.describe(
    event_id="Event to set reminders on",
    minutes='Comma-separated minutes before start, e.g. "10,30"',
)
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def reminders_set(
    interaction: discord.Interaction,
    event_id: str,
    minutes: str,
) -> None:
    """Handle reminders set — parse minutes, call add_reminders, respond."""
    calendar = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return

    try:
        parsed = parse_minutes(minutes)
    except ValueError as exc:
        await interaction.response.send_message(
            f"❌ {exc}", ephemeral=True
        )
        return

    try:
        calendar.add_reminders(event_id, parsed)
    except HttpError as exc:
        logger.error("Failed to set reminders on %s: %s", event_id, exc)
        error_msg = format_edit_error(exc)
        await interaction.response.send_message(error_msg, ephemeral=True)
        return

    display = _format_reminders_list(parsed)
    await interaction.response.send_message(
        f"✅ Reminders set: {display}"
    )


@reminders_group.command(
    name="show", description="Show current reminders on an event"
)
@app_commands.describe(event_id="Event to check reminders for")
@app_commands.autocomplete(event_id=delete_event_autocomplete)
async def reminders_show(
    interaction: discord.Interaction,
    event_id: str,
) -> None:
    """Handle reminders show — fetch event, display current reminder config."""
    calendar = interaction.client.calendar  # type: ignore[attr-defined]

    if calendar is None:
        await interaction.response.send_message(
            "❌ Calendar is not configured. Ask an admin to set "
            "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID.",
            ephemeral=True,
        )
        return

    try:
        event = calendar.get_event(event_id)
    except HttpError as exc:
        logger.error("Failed to get event %s: %s", event_id, exc)
        error_msg = format_edit_error(exc)
        await interaction.response.send_message(error_msg, ephemeral=True)
        return

    reminders = event.get("reminders", {})
    if reminders.get("useDefault", True):
        await interaction.response.send_message(
            "📋 No reminders set", ephemeral=True
        )
        return

    overrides = reminders.get("overrides", [])
    if not overrides:
        await interaction.response.send_message(
            "📋 No reminders set", ephemeral=True
        )
        return

    minutes_list = [o["minutes"] for o in overrides]
    display = _format_reminders_list(minutes_list)
    await interaction.response.send_message(
        f"📋 Reminders: {display}", ephemeral=True
    )


# ── /cal reminders-defaults ─────────────────────────────────────────────────


reminders_defaults_group = app_commands.Group(
    name="reminders-defaults",
    description="Default reminder settings for new events",
    parent=cal,
)


@reminders_defaults_group.command(
    name="set", description="Set default reminder minutes for new events"
)
@app_commands.describe(
    minutes='Comma-separated minutes before start, e.g. "10,30"'
)
async def reminders_defaults_set(
    interaction: discord.Interaction,
    minutes: str,
) -> None:
    """Store the user's default reminder configuration."""
    try:
        parsed = parse_minutes(minutes)
    except ValueError as exc:
        await interaction.response.send_message(
            f"❌ {exc}", ephemeral=True
        )
        return

    discord_id = str(interaction.user.id)
    interaction.client.settings.set(discord_id, "default_reminders", minutes)  # type: ignore[attr-defined]

    display = _format_reminders_list(parsed)
    await interaction.response.send_message(
        f"✅ Default reminders: {display}", ephemeral=True
    )


@reminders_defaults_group.command(
    name="show", description="Show your default reminder configuration"
)
async def reminders_defaults_show(
    interaction: discord.Interaction,
) -> None:
    """Display the user's stored default reminders, or a message if none."""
    discord_id = str(interaction.user.id)
    default = interaction.client.settings.get(discord_id, "default_reminders")  # type: ignore[attr-defined]

    if default:
        try:
            parsed = parse_minutes(default)
            display = _format_reminders_list(parsed)
            await interaction.response.send_message(
                f"📋 Default reminders: {display}", ephemeral=True
            )
        except ValueError:
            # Stored value is somehow invalid — show raw and let the
            # user re-set it.
            await interaction.response.send_message(
                f"📋 Default reminders: {default} "
                "(invalid format — use `/cal reminders-defaults set` to update)",
                ephemeral=True,
            )
    else:
        await interaction.response.send_message(
            "📋 No default reminders. "
            "Use `/cal reminders-defaults set` to configure one.",
            ephemeral=True,
        )
