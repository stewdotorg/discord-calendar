# Discal — Agent Context Index

## What is this?

Discal is a Discord bot for a server's **single shared Google Calendar**. The bot acts on that one calendar as **one Google account** (OAuth refresh token). Every command (create, show, edit, delete, list, invite, reminders) goes through those credentials. Users are invited by email as attendees and get normal Google invitation emails. The bot has **no access to users' own calendars**. Per-user settings (email, timezone, reminder defaults) live in SQLite. Python + discord.py + Google Calendar API, deployed with Docker Compose on a $4/mo DigitalOcean droplet.

## AI session rules (read first)

1. **Ask before touching code.** Don't edit files or run code-changing commands without explicit user approval.
2. **Work test-first.** Add or adjust pytest tests alongside every change. Run `pytest` and `ruff check src tests` before committing.
3. **Detect stale context.** If context files describe features or deployment state you can't confirm in the codebase, trust the canonical sources:
   - **GitHub Issues** (`gh issue list --state all`, repo `stewdotorg/discord-calendar`). Authoritative for issue state.
   - **`.env` and `.env.example`**. Authoritative for configuration, IDs, tokens. Reference them; don't duplicate values into context files.
   - **`git log` / `git diff`**. Authoritative for code history.
   - **Droplet** (`ssh discord-calendar-bot`). Authoritative for deployment state.

   Don't add issue state, commit summaries, or ephemeral deployment details to context files. Those belong in `.notes/` or the canonical sources. See the user-global AGENTS.md for the full policy.

## Quick pointers

| Thing | Key file |
|---|---|
| Main bot | `src/bot.py`: `DiscalClient` (intents, `on_message` DM replies, `on_interaction` RSVP buttons) |
| Commands | `src/commands/*.py` (see [commands](context/commands.md)) |
| Calendar (deep) | `src/calendar/service.py`: `CalendarService` |
| Auth (deep) | `src/calendar/auth.py`: OAuth user credentials |
| DB (deep) | `src/db/queries.py`: `SettingsStore` (user settings + pending invites) |
| DM invite flow | `src/dm_handler.py` |
| Utils | `src/utils.py`: parsing, formatting, mention resolution, `split_invitees`, `format_event_details` |
| Tests | `tests/`: pytest + VCR cassettes |
| GitHub | `stewdotorg/discord-calendar` |
| Droplet | `ssh discord-calendar-bot` → `/opt/discal/` |
| Config | `.env` (template and docs: `.env.example`) |
| Human docs | `README.md` (overview, commands), `SETUP.md` (self-hosting) |

## Index

| Topic | Summary | When to read | File |
|-------|---------|-------------|------|
| Architecture | Module map, auth model, key decisions | Understanding structure, design decisions | [architecture](context/architecture.md) |
| Commands | Command → file map, invite/RSVP/DM flows, gotchas | Adding or changing commands | [commands](context/commands.md) |
| Issues | Where issue state lives, labels | Checking or filing work | [issues](context/issues.md) |
| Deploying | Deploy commands, dev container, droplet gotchas | Deploying or debugging prod | [deploying](context/deploying.md) |
