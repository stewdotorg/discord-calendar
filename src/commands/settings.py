"""Commands for per-user email and timezone preferences under /cal."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import discord
from discord import app_commands

from src.commands.list_events import cal

settings_group = app_commands.Group(
    name="settings",
    description="Manage your calendar settings",
)

email_group = app_commands.Group(
    name="email",
    description="Set or show your stored email for RSVPs",
    parent=settings_group,
)

timezone_group = app_commands.Group(
    name="timezone",
    description="Set or show your timezone for event display",
    parent=settings_group,
)

# discord.py only supports one nesting level, so attach to cal manually.
cal.add_command(settings_group)


_INVALID_EMAIL_MSG = (
    "❌ Invalid email: {reason}. "
    "Please provide a valid email address, e.g. me@example.com."
)


def _validate_email(email: str) -> str | None:
    """Validate basic email format.

    Returns an error message string if invalid, or None if valid.
    """
    if "@" not in email:
        return _INVALID_EMAIL_MSG.format(reason="missing '@'")
    _, domain = email.rsplit("@", 1)
    if "." not in domain:
        return _INVALID_EMAIL_MSG.format(reason="domain missing '.'")
    return None


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


@email_group.command(name="set", description="Store your email for RSVPs")
@app_commands.describe(email="Your email address (e.g. me@example.com)")
async def email_set(interaction: discord.Interaction, email: str) -> None:
    """Store the user's email address after basic format validation."""
    error = _validate_email(email)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    discord_id = str(interaction.user.id)
    interaction.client.settings.set(discord_id, "email", email)
    await interaction.response.send_message(
        f"✅ Email stored: {email}", ephemeral=True
    )


@email_group.command(name="show", description="Show your stored email")
async def email_show(interaction: discord.Interaction) -> None:
    """Display the user's stored email, or a message if none is set."""
    discord_id = str(interaction.user.id)
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


@timezone_group.command(name="set", description="Store your timezone")
@app_commands.describe(timezone="An IANA timezone (e.g. America/Chicago)")
async def timezone_set(interaction: discord.Interaction, timezone: str) -> None:
    """Store the user's timezone after validating against the IANA database."""
    error = _validate_timezone(timezone)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    discord_id = str(interaction.user.id)
    interaction.client.settings.set(discord_id, "timezone", timezone)
    await interaction.response.send_message(
        f"✅ Timezone stored: {timezone}", ephemeral=True
    )


@timezone_group.command(name="show", description="Show your stored timezone")
async def timezone_show(interaction: discord.Interaction) -> None:
    """Display the user's stored timezone, or the default (US Eastern)."""
    discord_id = str(interaction.user.id)
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
