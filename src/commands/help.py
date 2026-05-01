"""/cal help command — show all available calendar commands."""

import discord

from src.commands.list_events import cal

_COMMANDS = [
    {
        "name": "/cal ping",
        "description": "Ping the bot",
        "example": "Check if the bot is online",
    },
    {
        "name": "/cal create",
        "description": "Create a Google Calendar event",
        "example": 'Create an event: /cal create title:"Team Sync" when:"May 1 3pm"',
    },
    {
        "name": "/cal today",
        "description": "List today's events",
        "example": "See all events scheduled for today",
    },
    {
        "name": "/cal delete",
        "description": "Delete a Google Calendar event",
        "example": "Remove an event by selecting it from the autocomplete dropdown",
    },
    {
        "name": "/cal help",
        "description": "Show all available calendar commands",
        "example": "Display this help message",
    },
]


@cal.command(name="help", description="Show all available calendar commands")
async def help_cmd(interaction: discord.Interaction) -> None:
    """Respond with an ephemeral embed listing all commands and examples."""
    embed = discord.Embed(
        title="📅 Discal — Calendar Commands",
        description="Use these slash commands to manage the shared calendar:",
        color=discord.Color.blue(),
    )

    for cmd in _COMMANDS:
        value = f"{cmd['description']}\n*Example: {cmd['example']}*"
        embed.add_field(name=cmd["name"], value=value, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
