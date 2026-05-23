# Commands

## Command structure

All commands register under the `cal` group:

| Command | File | Notes |
|---|---|---|
| `/cal ping` | `src/commands/ping.py` | Health check |
| `/cal create` | `src/commands/create.py` | Create events with NLP date parsing |
| `/cal today` | `src/commands/today.py` | List today's events |
| `/cal week` | `src/commands/week.py` | List this week's events |
| `/cal list` | `src/commands/list.py` | List events with date range |
| `/cal edit` | `src/commands/edit.py` | Edit event fields |
| `/cal delete` | `src/commands/delete.py` | Delete event by autocomplete selection |
| `/cal invite` | `src/commands/invite.py` | Add attendees via @mention, email, or `me` |
| `/cal rsvp` | `src/commands/rsvp.py` | RSVP yes/no/maybe via button on event post |
| `/cal settings` | `src/commands/settings.py` | Subgroup: `email set/show`, `timezone set/show` |
| `/cal reminders` | `src/commands/reminders.py` | Set calendar reminders |
| `/cal help` | `src/commands/help.py` | Command reference |

## Discord client cache bug

`discord.py` client cache may not contain members if the bot joined recently or the member hasn't sent a message. `resolve_mentions()` in `utils.py` handles both cached members and raw mentions parsed from the interaction data.
