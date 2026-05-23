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
| Prod env | `.env` (current bot; will rename to `.env.prod` in #35) |
| Dev env | `.env.dev` (separate Discord app + calendar; auto-spindown via #35) |

## Index

| Topic | Summary | When to read | File |
|-------|---------|-------------|------|
| Architecture | Full orientation table, deep module map, key architectural decisions (1–5) | Understanding codebase structure, making design decisions | [architecture](context/architecture.md) |
| Sandcastle | AFK workflow config, run, logs, limitations, reviewer-only, infinite-loop guard | Preparing or dispatching AFK issues | [sandcastle](context/sandcastle.md) |
| Issues | Current issue state, closed/completed, open items | Checking what's done and what's pending | [issues](context/issues.md) |
| Commands | Full command structure and Discord client cache bug | Adding/changing commands, debugging command visibility | [commands](context/commands.md) |
| Deploying | Deploy steps, dev container, auto-shutdown/update, isolation | Deploying to production, managing dev container | [deploying](context/deploying.md) |
