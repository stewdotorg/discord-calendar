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
| Droplet | `ssh discord-calendar-bot` → `/opt/discal/` — two containers: prod (`bot`, :8000) and dev (`bot-dev`, :8001, auto-spindown) |
| Deployment guide | `.ignore/deploying.md` |
| Beta release guide | `.ignore/beta-release.md` |

## Key architectural decisions

1. **`copy_global_to(guild=guild)` before `sync`:** Commands are registered globally via side-effect imports. Without `copy_global_to`, `sync(guild=guild)` pushes zero commands. This was a hard-won bug. The test in `test_bot_setup.py` guards against regression. ⚠️ **Superseded by #29:** moving to `add_command(cal, guild=guild)` — commands registered directly on the guild tree, no global dance. Update this entry once #29 lands.

2. **OAuth2, not service account:** Service accounts can't manage attendees on `@group.calendar.google.com` calendars. The bot uses OAuth2 user credentials with a stored `GOOGLE_REFRESH_TOKEN`.

3. **`sendUpdates="all"`:** Google Calendar sends invitation emails when attendees are added. Changed from `"none"` (old service-account workaround) to `"all"` in #26.

4. **Partial invite success:** When `/cal invite` or `/cal create invite:` encounters invalid entries (unset email, bad format), valid entries still get added. Warnings are shown for bad entries.

5. **No new deep-module methods for features:** `add_attendees()` and `SettingsStore.get()` already exist. New features are wiring, not deep changes.
