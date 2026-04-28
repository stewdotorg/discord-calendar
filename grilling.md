# Discal — Grill Me Session

## Final Design Tree

| # | Decision | Answer |
|---|---|---|
| 1 | Source of truth | Google Calendar |
| 2 | Whose calendar | Single shared calendar via service account |
| 3 | Operations | CRUD + date-range list |
| 4 | Command style | Slash commands |
| 5 | Hosting | Cheap VPS ($5–6/mo) |
| 6 | Guild scope | Single server (designed for multi-guild later) |
| 7 | Date/time input | Structured pickers + optional `when` text; `when` overrides pickers |
| 8 | Language | Python + discord.py |
| 9 | Local state | SQLite with Docker volume mount (for settings, not events) |
| 10 | Ownership | Open model (anyone can edit/delete any event) |
| 11 | Reminders | Per-user defaults + per-event overrides + channel reminders |
| 12 | Reminder surface | `/cal settings reminders` (defaults) + `/cal reminders <event>` |
| 13 | User prefs | Reminder defaults + timezone (fallback: user → US Eastern → UTC) |
| 14 | Reminder delivery | Google Calendar native notifications + channel messages |
| 15 | Channel reminders | Per-event announcements + daily/weekly/monthly digest |
| 16 | Digest format | Discord embed |
| 17 | Scheduler | asyncio background loop (~60s poll) |
| 18 | Event selection | Discord slash command autocomplete (live Google Calendar query) |
| 19 | Natural language | `dateparser` library |
| 20 | Local dev | `cloudflared tunnel --url http://localhost:8000` |
| 21 | Calendar config | Hardcoded calendar ID in `.env` |
| 22 | Event description | Optional `description:` field |
| 23 | Duration | Optional `duration:` in minutes, default 60 |
| 24 | Search | Date range + optional title filter (`q` parameter) |
| 25 | Error handling | Specific error messages + single silent retry on transient failures |
| 26 | Audit trail | Google Calendar `extendedProperties.private` (createdBy, lastEditedBy) |
| 27 | Deploy | Manual (`git pull && docker compose up -d`) |
| 28 | Discord intents | Minimum (no privileged intents) |
| 29 | Google auth | Service account (JSON key file) |
| 30 | Help | `/cal help` (ephemeral embed) + Discord picker descriptions |
| 31 | GitHub repo | Set up during this session |
| 32 | First AFK scope | MVP: ping, auth, create, today, delete |
| 33 | Invite/RSVP surface | `/cal invite <event> emails:...`, `/cal rsvp <event> [email:]`, `/cal settings email` |
| 34 | RSVP email source | Stored in SQLite; prompted to set on first RSVP; per-call override supported |
| 35 | Multi-invite | Comma-separated `emails:` string, single Google API call |
| 36 | Attendee display in Discord | Deferred to later tick |
| 37 | Delete with attendees | Silent delete (Google sends cancellation emails automatically) |

---

## Full Command Surface

### Event Commands

| Command | Description |
|---|---|
| `/cal ping` | Bot responds "pong" (connectivity check) |
| `/cal create title:"..." date:... time:... [duration:60] [description:"..."] [invite:emails]` | Create event with optional attendees |
| `/cal today` | List today's events |
| `/cal week` | List this week's events |
| `/cal list from:... to:... [search:"..."]` | List events in date range, optional title filter |
| `/cal edit <event>` | Edit an existing event (title, date, time, duration, description) |
| `/cal delete <event>` | Delete an event (sends cancellation to attendees) |

### Invite/RSVP

| Command | Description |
|---|---|
| `/cal invite <event> emails:alice@x.com,bob@y.com` | Add attendees to an event |
| `/cal rsvp <event> [email:override]` | RSVP with stored email (prompts to set if unset) |
| `/cal settings email set me@example.com` | Store your email address |
| `/cal settings email show` | Show stored email address |

### Reminders

| Command | Description |
|---|---|
| `/cal reminders <event> add <minutes>` | Add reminder to specific event |
| `/cal reminders <event> list` | List reminders on specific event |
| `/cal reminders <event> remove <reminder>` | Remove a reminder from specific event |

### User Settings

| Command | Description |
|---|---|
| `/cal settings reminders add <minutes>` | Set a per-user default reminder |
| `/cal settings reminders list` | Show your default reminders |
| `/cal settings reminders remove <reminder>` | Remove a per-user default reminder |
| `/cal settings timezone <tz>` | Set your timezone |
| `/cal settings email set me@example.com` | Store your email |
| `/cal settings email show` | Show stored email |

### Digest

| Command | Description |
|---|---|
| `/cal digest set period:daily\|weekly\|monthly [channel:#chan] time:09:00` | Enable digest. Channel defaults to current channel. |
| `/cal digest disable [period:daily\|weekly\|monthly] [channel:#chan]` | Disable digest(s). Channel defaults to current channel. |
| `/cal digest list` | Show active digests for the server |

### Help

| Command | Description |
|---|---|
| `/cal help` | Ephemeral embed with all commands and usage examples |

---

## MVP Scope (First Sandcastle Night Shift)

Five vertical tracer bullets, each a GitHub issue labeled `ready-for-agent`:

| Issue | Command | Tracer bullet |
|---|---|---|
| #1 | `/cal ping` | "pong" — proves Discord app, Interactions Endpoint, slash command registration |
| #2 | (internal) | Google Calendar auth via service account, connection verified |
| #3 | `/cal create title:"..." date:... time:... [duration:...] [description:...]` | Event appears in Google Calendar |
| #4 | `/cal today` | Lists today's events from Google Calendar via autocomplete picker |
| #5 | `/cal delete <event>` | Removes event from Google Calendar, autocomplete shows existing events |

Dependency DAG:

```
#1 (ping) → #2 (auth) → #3 (create)
                        → #4 (today)
                        → #5 (delete) [depends on #3 — needs events to delete]
```

---

## Second Tick (Post-MVP)

| Issue | Command |
|---|---|
| #6 | `/cal week`, `/cal list from:... to:... [search:...]` |
| #7 | `/cal edit <event>` |
| #8 | `/cal settings email`, `/cal rsvp`, `/cal invite` |
| #9 | `/cal settings reminders`, `/cal reminders <event>` |
| #10 | `/cal settings timezone` |
| #11 | `/cal digest set/disable/list` + scheduler loop |
| #12 | `/cal help` |
| #13 | Natural language `when:` field via `dateparser` |
| #14 | `invite:` on `/cal create`, audit trail in extendedProperties |
