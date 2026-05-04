"""Commands for per-user email and timezone preferences under /cal.

Refactored to <verb> <noun> pattern so new settings can be added as
``settings set <noun>`` and ``settings show <noun>`` without name collisions.
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


# ── shared setting choices ────────────────────────────────────────────────────

_SETTING_CHOICES = [
    app_commands.Choice(name="email", value="email"),
    app_commands.Choice(name="timezone", value="timezone"),
]

_UNKNOWN_SETTING_MSG = "❌ Unknown setting: {setting}. Try: email, timezone"


# ── /cal settings set ─────────────────────────────────────────────────────────


@settings_group.command(name="set", description="Set a calendar setting")
@app_commands.describe(
    setting="The setting to change (email or timezone)",
    value="The value to store",
)
@app_commands.choices(setting=_SETTING_CHOICES)
async def set_settings(
    interaction: discord.Interaction,
    setting: str,
    value: str | None = None,
) -> None:
    """Handle setting a value for email or timezone."""
    discord_id = str(interaction.user.id)

    if setting == "email":
        if not value:
            await interaction.response.send_message(
                "❌ Please provide an email address. "
                "Usage: `/cal settings set email me@example.com`",
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
    elif setting == "timezone":
        if not value:
            await interaction.response.send_message(
                "❌ Please provide a timezone. "
                "Usage: `/cal settings set timezone America/Chicago`",
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
    else:
        await interaction.response.send_message(
            _UNKNOWN_SETTING_MSG.format(setting=setting), ephemeral=True
        )


# ── /cal settings show ────────────────────────────────────────────────────────


@settings_group.command(name="show", description="Show a calendar setting")
@app_commands.describe(
    setting="The setting to display (email or timezone)",
)
@app_commands.choices(setting=_SETTING_CHOICES)
async def show_settings(
    interaction: discord.Interaction,
    setting: str,
) -> None:
    """Handle showing a value for email or timezone."""
    discord_id = str(interaction.user.id)

    if setting == "email":
        email = interaction.client.settings.get(discord_id, "email")
        if email:
            await interaction.response.send_message(
                f"📧 Your stored email: {email}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "📧 No email set. Use `/cal settings set email` to store one.",
                ephemeral=True,
            )
    elif setting == "timezone":
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
            _UNKNOWN_SETTING_MSG.format(setting=setting), ephemeral=True
        )
