# Discal — Discord Google Calendar Bot

A Discord slash-command bot that reads and writes to a shared Google Calendar.
Discord is the UI; Google Calendar is the source of truth.

## Architecture

```
discord (slash commands) → bot (Python) → Google Calendar API
                               ↕
                          SQLite (user settings)
```

## Commands

| Command | Description |
|---|---|
| `/cal ping` | Bot responds "pong" (connectivity check) |
| `/cal create title:"..." date:YYYY-MM-DD time:HH:MM [duration:60] [description:"..."]` | Create a Google Calendar event |
| `/cal today` | List today's events |
| `/cal delete <event>` | Delete an event (autocomplete picks from existing events) |

All commands are registered under the `/cal` group.

## Quick Start

### Prerequisites

- Python 3.12+
- Discord bot application ([Developer Portal](https://discord.com/developers/applications))
- Google Cloud service account with Calendar API enabled
- A Google Calendar shared with the service account email

### 1. Clone and configure

```bash
git clone git@github.com:stewdotorg/discord-calendar.git
cd discord-calendar
cp .env.example .env
# Edit .env with your values
pip install -r requirements.txt
```

### 2. Environment variables (`.env`)

| Variable | Source |
|---|---|
| `DISCORD_TOKEN` | Developer Portal → Bot → Token |
| `DISCORD_APPLICATION_ID` | Developer Portal → General Information |
| `DISCORD_PUBLIC_KEY` | Developer Portal → General Information |
| `DISCORD_GUILD_ID` | Right-click server → Copy ID (Developer Mode) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to downloaded service account JSON key |
| `GOOGLE_CALENDAR_ID` | Google Calendar → Settings → Integrate calendar → Calendar ID |
| `HOST` | `0.0.0.0` |
| `PORT` | `8000` |

### 3. Run locally

```bash
# Terminal 1: expose a public URL for Discord's Interactions Endpoint
cloudflared tunnel --url http://localhost:8000

# Terminal 2: run the bot
python src/bot.py
```

Then set the Interactions Endpoint URL in the Discord Developer Portal to
`https://your-tunnel.trycloudflare.com/interactions`.

### 4. Deploy to a VPS

```bash
# On the VPS
git clone git@github.com:stewdotorg/discord-calendar.git
cd discord-calendar
cp .env.example .env
# Edit .env with your values
# Copy service-account.json to the project root
# Edit Caddyfile: replace "your.domain" with your actual domain

docker compose up -d
```

## Development

### Running tests

```bash
python -m pytest tests/ -v
```

### Sandcastle (AI agent orchestration)

This project uses [Sandcastle](https://github.com/mattpocock/sandcastle) to run AI coding
agents that implement GitHub issues via TDD in isolated Docker sandboxes.

```bash
# One-time setup
cp .sandcastle/.env.example .sandcastle/.env
# Edit .sandcastle/.env: DEEPSEEK_API_KEY and GH_TOKEN

# Run the night shift
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
npm run sandcastle
```

The orchestrator follows a three-phase loop:

1. **Planner** — reads `ready-for-agent` issues, builds dependency graph, picks unblocked work
2. **Implementer + Reviewer** — parallel Docker sandboxes, TDD on each issue
3. **Merger** — merges branches, runs tests, pushes feature branches, closes issues

## Design Decisions

See [grilling.md](grilling.md) for the full design tree (37 decisions) and
[PRD.md](PRD.md) for the product requirements document.

| Decision | Choice |
|---|---|
| Source of truth | Google Calendar |
| Calendar auth | Service account (JSON key) |
| Discord style | Slash commands |
| Language | Python 3.12+ / discord.py |
| Local storage | SQLite (Docker volume mount) |
| Bot scope | Single server (multi-guild ready) |
| Model | Open (anyone can edit/delete any event) |
| Timezone | User → US Eastern → UTC |

## License

MIT
