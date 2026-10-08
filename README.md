# Discal — Discord Google Calendar Bot

A Discord slash-command bot for a server's **single shared Google Calendar**.
Discord is the UI; Google Calendar is the source of truth.

## How it works

- **One bot, one calendar.** Each bot deployment manages exactly one Google
  Calendar (`GOOGLE_CALENDAR_ID`), and is registered to exactly one Discord
  server (`DISCORD_GUILD_ID`).
- **The bot acts as its own Google account.** Every command (create, edit,
  delete, list, invite, reminders) runs against that shared calendar using
  the bot's Google credentials (an OAuth refresh token for one Google
  account, authorized once with `scripts/setup_oauth.py`). Discord users
  never sign in to Google.
- **People receive invites; the bot never touches their calendars.** Inviting
  someone adds their email as an attendee on the shared calendar's event, and
  Google emails them a normal calendar invitation. Whether it appears on their
  own calendar is up to them and their Google settings. The bot has no access
  to anyone's personal calendar.
- **Discord users are mapped to emails.** To invite someone by @mention, the
  bot needs their email. Users store it with `/cal settings set`, by clicking
  the 📅 invite button on an event post, or by replying to the bot's DM when
  they're @mentioned before their email is on file.

```
Discord (slash commands, buttons, DMs)
        │
        ▼
   bot (Python, discord.py) ── SQLite: per-user email, timezone, reminder defaults
        │
        ▼  bot's own Google account (OAuth)
Google Calendar API ── the one shared calendar ── invitation emails → attendees
```

## Commands

All commands live under `/cal`. Commands that take `event:` autocomplete from
upcoming events on the shared calendar.

### Events

| Command | What it does |
|---|---|
| `/cal create title: when: [duration:] [description:] [invite:]` | Create an event. `when` is natural language in your timezone (default US Eastern), e.g. `tomorrow 2pm`, `May 1 3pm`, `tomorrow 2-4pm`. `duration` defaults to 60 min. |
| `/cal show event:` | Show an event's current details, with a button to post it to the channel. Use it to re-advertise an event after a lot of scrollback. |
| `/cal edit event: [title:] [when:] [duration:] [description:]` | Change an event. |
| `/cal delete event:` | Delete an event. |
| `/cal today` | List today's events. |
| `/cal week` | List the next 7 days of events. |
| `/cal list from: to: [search:]` | List events in a date range (`YYYY-MM-DD`), optionally filtered by keyword. |

Responses are only visible to you at first. A **📢 Post to channel** button
publishes them. When you post an event from `/cal create` or `/cal show`, the
public post includes a **📅 Email me a calendar invite** button anyone can click.

### Invites

| Command | What it does |
|---|---|
| `/cal invite event: people:` | Add attendees. `people` takes `me`, @mentions, and email addresses, separated by spaces or commas (e.g. `me @chaz alice@example.com`). |
| `/cal create … invite:` | Same `people` syntax, applied at creation. |

If an @mentioned user has no email on file, the bot DMs them asking for it.
When they reply with their email, it's saved and they're added to the event.
This needs the Message Content intent; see [SETUP.md](SETUP.md).

### Settings and reminders

| Command | What it does |
|---|---|
| `/cal settings set setting:email value:` | Store your email (used for invites). |
| `/cal settings set setting:timezone value:` | Store your timezone, e.g. `America/Chicago`. |
| `/cal settings show setting:` | Show a stored setting. |
| `/cal reminders set event: minutes:` | Set popup reminders, e.g. `10,30`. |
| `/cal reminders show event:` | Show an event's reminders. |
| `/cal reminders-defaults set minutes:` | Default reminders applied to events you create. |
| `/cal reminders-defaults show` | Show your default reminders. |
| `/cal help` | List all commands. |
| `/cal ping` | Connectivity check. |

## Quick start

Full instructions, including the Google and Discord setup: **[SETUP.md](SETUP.md)**.

```bash
git clone git@github.com:stewdotorg/discord-calendar.git discal
cd discal
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # fill in Discord + calendar values
python scripts/setup_oauth.py     # authorize the bot's Google account → writes GOOGLE_REFRESH_TOKEN
python -m src.bot
```

The bot holds an outbound WebSocket connection to Discord. It runs no HTTP
server, so no tunnel, domain or open port is needed.

## Configuration (`.env`)

`.env.example` is the template and documents each variable.

| Variable | Purpose |
|---|---|
| `DISCORD_TOKEN` | Bot token (Developer Portal → Bot). |
| `DISCORD_APPLICATION_ID` | Developer Portal → General Information. |
| `DISCORD_PUBLIC_KEY` | Developer Portal → General Information. |
| `DISCORD_GUILD_ID` | The one server the bot serves (right-click server → Copy Server ID). |
| `DISCORD_ENABLE_MESSAGE_CONTENT` | Keep `true`. Required for DM email replies; off if unset. |
| `DISCORD_NOTIFY_TARGETS` / `DISCORD_NOTIFY_EVENTS` | Optional restart/shutdown/error/deploy notifications to channels (`c:<id>`) or users (`u:<id>`). |
| `GOOGLE_CALENDAR_ID` | The shared calendar (ends in `@group.calendar.google.com`). |
| `GOOGLE_CLIENT_SECRET_FILE` | OAuth client JSON (default `./client-secret.json`). |
| `GOOGLE_REFRESH_TOKEN` | The bot account's token, written by `scripts/setup_oauth.py`. |
| `AUTOCOMPLETE_LOOKAHEAD_DAYS` | How far ahead event autocomplete looks (code default 14; template sets 90). |

## Development

```bash
python -m pytest tests/            # unit tests + VCR cassette playback (no network)
python -m pytest tests/ --record   # re-record cassettes against the live API
ruff check src tests
```

VCR integration tests (`tests/test_calendar_vcr.py`) replay recorded Google
Calendar API traffic from `tests/cassettes/`. Recording needs
`GOOGLE_REFRESH_TOKEN` and `GOOGLE_CALENDAR_ID`.

## Design decisions

| Decision | Choice |
|---|---|
| Source of truth | Google Calendar. The bot stores no events, only per-user settings. |
| Calendar scope | One shared calendar per bot deployment. |
| Google identity | One Google account authorized via OAuth (refresh token). |
| Access to users' calendars | None. Users only receive invitation emails. |
| Discord scope | One server, guild-registered slash commands. |
| Permission model | Open: anyone in the server can create, edit or delete any event. |
| Timezone | Per-user, falling back to US Eastern. |
| Storage | SQLite on a Docker volume. |
| Deployment | Docker Compose on a small VPS. See [SETUP.md](SETUP.md). |

## License

MIT
