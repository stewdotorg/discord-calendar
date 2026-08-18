# Architecture

## Full orientation

| Thing | Location |
|---|---|
| Project root | `~/dev/discal/` |
| Main bot | `src/bot.py` — `DiscalClient` subclass of `discord.Client` |
| Commands | `src/commands/*.py` — each registers on the `cal` group |
| Deep module: calendar | `src/calendar/service.py` — `CalendarService` (create/update/delete events, add attendees, reminders) |
| Deep module: DB | `src/db/queries.py` — `SettingsStore` (SQLite per-user settings) |
| Deep module: auth | `src/calendar/auth.py` — OAuth2 credential loading |
| Utils | `src/utils.py` — parsing, formatting, mention resolution |
| Tests | `tests/` — pytest + VCR cassettes for Google API |
| GitHub | `stewdotorg/discord-calendar` |
| Droplet | `ssh discord-calendar-bot` → `/opt/discal/` — two containers: prod (`bot`) and dev (`bot-dev`, auto-spindown) |
| Config | `.env` (see `.env.example` for full docs) — authoritative for app IDs, guild IDs, tokens, calendar ID |
| Deployment guide | `.ignore/deploying.md` |
| Beta release guide | `.ignore/beta-release.md` |

## Key architectural decisions

1. **Commands registered via `add_command(cal, guild=guild)`:** Commands are registered directly on the guild tree (guild-only mode), then an empty global sync purges stale global commands from prior deploys. The test in `test_bot_setup.py` guards against silently syncing zero commands.

2. **OAuth2, not service account:** Service accounts can't manage attendees on `@group.calendar.google.com` calendars. The bot uses OAuth2 user credentials with a stored `GOOGLE_REFRESH_TOKEN`.

3. **`sendUpdates="all"`:** Google Calendar sends invitation emails when attendees are added. Changed from `"none"` (old service-account workaround) to `"all"` in #26.

4. **Partial invite success:** When `/cal invite` or `/cal create invite:` encounters invalid entries (unset email, bad format), valid entries still get added. Warnings are shown for bad entries.

5. **No new deep-module methods for features:** `add_attendees()` and `SettingsStore.get()` already exist. New features are wiring, not deep changes.

6. **WebSocket-only client — no HTTP server:** The bot makes an outbound connection to Discord's gateway and runs no inbound HTTP listener. The `HEALTHCHECK`, `EXPOSE 8000`, `HOST`/`PORT` env vars, and the Caddy reverse proxy (`discal.ztu.fm`) were stale scaffolding from the initial template and were removed (Aug 2026). There is no `/health` endpoint and no inbound port — don't re-add them.
