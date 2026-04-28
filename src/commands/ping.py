"""Ping command — tracer bullet for Discord connectivity."""

import discord
from discord import app_commands


@app_commands.command(name="ping", description="Ping the bot")
async def ping(interaction: discord.Interaction) -> None:
    """Respond with 'pong' to prove the bot is alive."""
    await interaction.response.send_message("pong", ephemeral=True)
