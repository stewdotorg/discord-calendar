"""Commands for per-user email and timezone preferences under /cal.

Refactored to <param> <verb> pattern so new settings (reminders,
subgroups, …) can be added as ``settings <param> <verb>`` without
name collisions.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import discord
from discord import app_commands

from src.commands.list_events import cal
from src.utils import validate_email

settings_group = app_commands.Group(
    name="settings",
    description="Manage your calendar settings",
    parent=cal,
)


def _validate_timezone(tz_str: str) -> str | None:
    """Validate a timezone string against the IANA database.

    Returns an error message string if invalid, or None if valid.
    """
    try:
        ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        available = ", ".join(sorted(available_timezones())[:5])
        return (
            f"❌ Invalid timezone '{tz_str}'. "
            f"Use an IANA timezone like America/Chicago or US/Eastern. "
            f"Examples: {available}, …"
        )
    return None


# ── shared verb choices ──────────────────────────────────────────────────────

_VERB_CHOICES = [
    app_commands.Choice(name="set", value="set"),
    app_commands.Choice(name="show", value="show"),
]

_UNKNOWN_ACTION_MSG = "❌ Unknown action: {action}. Try: set, show"


# ── /cal settings email ──────────────────────────────────────────────────────


@settings_group.command(name="email", description="Manage your email address")
@app_commands.describe(
    action="What to do with your email (set or show)",
    value="Your email address (required for 'set')",
)
@app_commands.choices(action=_VERB_CHOICES)
async def email_settings(
    interaction: discord.Interaction,
    action: str,
    value: str | None = None,
) -> None:
    """Handle email set and show."""
    discord_id = str(interaction.user.id)

    if action == "set":
        if not value:
            await interaction.response.send_message(
                "❌ Please provide an email address. "
                "Usage: `/cal settings email set me@example.com`",
                ephemeral=True,
            )
            return
        error = validate_email(value)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        interaction.client.settings.set(discord_id, "email", value)
        await interaction.response.send_message(
            f"✅ Email stored: {value}", ephemeral=True
        )
    elif action == "show":
        email = interaction.client.settings.get(discord_id, "email")
        if email:
            await interaction.response.send_message(
                f"📧 Your stored email: {email}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "📧 No email set. Use `/cal settings email set` to store one.",
                ephemeral=True,
            )
    else:
        await interaction.response.send_message(
            _UNKNOWN_ACTION_MSG.format(action=action), ephemeral=True
        )


# ── /cal settings timezone ───────────────────────────────────────────────────


@settings_group.command(name="timezone", description="Manage your timezone")
@app_commands.describe(
    action="What to do with your timezone (set or show)",
    value="An IANA timezone (required for 'set', e.g. America/Chicago)",
)
@app_commands.choices(action=_VERB_CHOICES)
async def timezone_settings(
    interaction: discord.Interaction,
    action: str,
    value: str | None = None,
) -> None:
    """Handle timezone set and show."""
    discord_id = str(interaction.user.id)

    if action == "set":
        if not value:
            await interaction.response.send_message(
                "❌ Please provide a timezone. "
                "Usage: `/cal settings timezone set America/Chicago`",
                ephemeral=True,
            )
            return
        error = _validate_timezone(value)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        interaction.client.settings.set(discord_id, "timezone", value)
        await interaction.response.send_message(
            f"✅ Timezone stored: {value}", ephemeral=True
        )
    elif action == "show":
        timezone = interaction.client.settings.get(discord_id, "timezone")
        if timezone:
            await interaction.response.send_message(
                f"🕐 Your timezone: {timezone}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "🕐 No timezone set. Defaulting to US Eastern.",
                ephemeral=True,
            )
    else:
        await interaction.response.send_message(
            _UNKNOWN_ACTION_MSG.format(action=action), ephemeral=True
        )
