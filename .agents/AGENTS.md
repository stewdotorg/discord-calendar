# Discal — Agent Context Index

## What is this?

Discal is a Discord bot that manages a shared Google Calendar. Users create/edit/delete events, invite people by @mention or email, set reminders, and store per-user settings (email, timezone). Python + discord.py + Google Calendar API. Deployed on a $4/mo DigitalOcean droplet.

## AI session rules (read first)

1. **Ask before touching code.** Do not make edits or run code-changing commands without explicit user approval.
2. **All code changes go through the Sandcastle AFK workflow.** Prepare a ticket → get approval → dispatch `npm run sandcastle`. Never implement directly.
3. **Run Sandcastle in the background.** `npm run sandcastle` takes minutes; run it with a long timeout or let it time out after the implementer starts. Give the user the `tail -f` command to watch progress:
   ```bash
   tail -f .sandcastle/logs/sandcastle-issue-<N>-<slug>-implementer.log
   ```
4. **GitHub labels:** `ready-for-agent` = Sandcastle can pick it up. `needs-triage` = human review needed first. Never mark an issue `ready-for-agent` without confirming with the user.
5. **Detect stale context.** If context files describe issues, features, or deployment state that you cannot confirm exists in the codebase, your local view may be stale. The canonical sources of truth are:
   - **GitHub Issues** (`gh issue list --state all` — `stewdotorg/discord-calendar`) — authoritative for ALL issue state (open AND closed); parallel sessions may have completed work you're unaware of
   - **`.env` and `.env.example`** — authoritative for configuration, IDs, tokens; reference these, don't duplicate them in context files
   - **`git log` and `git diff`** — authoritative for code history and current state
   - **Droplet** (`ssh discord-calendar-bot`) — authoritative for deployment state

   When context conflicts with a canonical source, trust the canonical source. **Do not add issue state, commit summaries, or ephemeral deployment details to context files** — these belong in `.notes/` handoff files or canonical sources, not in persistent agent context. See user-global AGENTS.md for the full context-content policy.

## Quick pointers

| Thing | Key file |
|---|---|
| Main bot | `src/bot.py` — `DiscalClient` |
| Commands | `src/commands/*.py` |
| Calendar (deep) | `src/calendar/service.py` |
| DB (deep) | `src/db/queries.py` |
| Auth (deep) | `src/calendar/auth.py` |
| Utils | `src/utils.py` |
| Tests | `tests/` — pytest + VCR cassettes |
| GitHub | `stewdotorg/discord-calendar` |
| Droplet | `ssh discord-calendar-bot` → `/opt/discal/` |
| Config | `.env` (see `.env.example` for docs) — authoritative for app IDs, guild IDs, tokens, calendar ID |

## Index

| Topic | Summary | When to read | File |
|-------|---------|-------------|------|
| Architecture | Deep module map, key architectural decisions | Understanding codebase structure, making design decisions | [architecture](context/architecture.md) |
| Sandcastle | AFK workflow, gotchas (GH_TOKEN), reviewer-only, offgassing | Preparing or dispatching AFK issues | [sandcastle](context/sandcastle.md) |
| Issues | Canonical source reference — never list individual issues here | Checking what's open | [issues](context/issues.md) |
| Commands | Full command structure and Discord client cache bug | Adding/changing commands, debugging command visibility | [commands](context/commands.md) |
| Deploying | Deploy commands, gotchas, droplet management | Deploying to production | [deploying](context/deploying.md) |
