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
        "name": "/cal week",
        "description": "List events for the next 7 days",
        "example": "See everything coming up this week",
    },
    {
        "name": "/cal list",
        "description": "List events in a custom date range",
        "example": '/cal list from:2026-05-01 to:2026-05-15 search:standup',
    },
    {
        "name": "/cal edit",
        "description": "Edit a Google Calendar event",
        "example": 'Change an event title: /cal edit event:<pick> title:"New Title"',
    },
    {
        "name": "/cal invite me",
        "description": "Add yourself as an attendee",
        "example": "Add yourself to an event: /cal invite me event:<pick> or with email: /cal invite me event:<pick> email:me@example.com",
    },
    {
        "name": "/cal invite by-email",
        "description": "Invite others to an event by email",
        "example": "Invite others: /cal invite by-email event:<pick> emails:alice@example.com, bob@example.com",
    },
    {
        "name": "/cal reminders set",
        "description": "Set reminders on an event",
        "example": 'Add reminders: /cal reminders set event:<pick> minutes:"10,30"',
    },
    {
        "name": "/cal reminders show",
        "description": "Show current reminders on an event",
        "example": 'Check reminders: /cal reminders show event:<pick>',
    },
    {
        "name": "/cal reminders-defaults set",
        "description": "Set default reminder minutes for new events",
        "example": 'Store default: /cal reminders-defaults set minutes:"10,30"',
    },
    {
        "name": "/cal reminders-defaults show",
        "description": "Show your default reminder configuration",
        "example": 'Check defaults: /cal reminders-defaults show'
    },
    {
        "name": "/cal help",
        "description": "Show all available calendar commands",
        "example": "Display this help message",
    },
    {
        "name": "/cal settings set email",
        "description": "Store your email for RSVPs",
        "example": '/cal settings set email me@example.com',
    },
    {
        "name": "/cal settings show email",
        "description": "Show your stored email",
        "example": '/cal settings show email',
    },
    {
        "name": "/cal settings set timezone",
        "description": "Store your timezone for event display",
        "example": '/cal settings set timezone America/Chicago',
    },
    {
        "name": "/cal settings show timezone",
        "description": "Show your stored timezone",
        "example": '/cal settings show timezone',
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
