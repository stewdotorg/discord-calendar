# Architecture

## Mental model

- **One deployment = one Discord server + one shared Google Calendar.** `DISCORD_GUILD_ID` and `GOOGLE_CALENDAR_ID` in `.env`.
- **The bot is one Google identity.** `src/calendar/auth.py` loads OAuth user credentials from `GOOGLE_REFRESH_TOKEN` + `client-secret.json`. All calendar operations, for every Discord user, run as that account.
- **Users are attendees, never calendar owners.** Inviting adds an attendee email to the shared calendar's event (`sendUpdates="all"`), and Google emails them. The bot can't read or write anyone's personal calendar.
- **Discord identity → email** is the only user mapping, stored in SQLite (`user_settings`, key `email`).

## Module map

| Thing | Location |
|---|---|
| Main bot | `src/bot.py`: `DiscalClient` subclass of `discord.Client` |
| Commands | `src/commands/*.py`, each registers on the `cal` group (see [commands](commands.md)) |
| Deep module: calendar | `src/calendar/service.py`: `CalendarService` (create/get/update/delete events, attendees, reminders) |
| Deep module: DB | `src/db/queries.py`: `SettingsStore` (per-user settings, pending invites with 7-day expiry) |
| Deep module: auth | `src/calendar/auth.py`: credential loading |
| DM invite flow | `src/dm_handler.py`: send "reply with your email" DMs, process replies |
| Views | `src/views.py`: `PostToChannelView`; `src/commands/rsvp.py`: `RsvpView` |
| Utils | `src/utils.py`: date parsing, formatting, mention resolution |
| Tests | `tests/`: pytest + VCR cassettes for Google API |

## Key architectural decisions

1. **OAuth user credentials.** The bot authenticates as one Google account via `GOOGLE_REFRESH_TOKEN` + `client-secret.json`, which lets it add attendees and send invitations.

2. **Commands registered via `add_command(cal, guild=guild)`.** Guild-only registration, then an empty global sync purges stale global commands from earlier deploys. `test_bot_setup.py` guards against silently syncing zero commands.

3. **`sendUpdates="all"`.** Google sends invitation emails when attendees are added (changed from `"none"` in #26).

4. **Partial invite success.** `/cal invite` and `/cal create invite:` add the valid entries and warn about the bad ones (unset email, bad format).

5. **Message Content intent is opt-in in code.** `DISCORD_ENABLE_MESSAGE_CONTENT` defaults to off when unset. This is deliberate: keep it off in code, on in every `.env`. When off, `on_message` drops DM replies silently, so users can't complete the "reply with your email" flow.

6. **Shared event formatting.** `format_event_details()` renders the public event block for both `/cal create` and `/cal show`, so the two stay identical.

7. **WebSocket-only client, no HTTP server.** The bot connects out to Discord's gateway and runs no inbound listener. The old `HEALTHCHECK`, `EXPOSE 8000`, `HOST`/`PORT` and Caddy reverse proxy (`discal.ztu.fm`) were stale template scaffolding and were removed (Aug 2026). Don't re-add them.
