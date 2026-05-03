# Discal — Setup Guide

A step-by-step guide to deploy your own instance of Discal, a Discord bot that reads and writes to a shared Google Calendar.

**Prerequisites:** A domain name, a server (or Docker-capable machine), a Discord application, and a Google Cloud project.

---

## 1. Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → name it (e.g. "Discal")
2. **Bot** tab → **Add Bot** → **Reset Token** and copy it (you'll paste into `.env` later)
3. Under **Privileged Gateway Intents**: nothing needed (slash commands only)
4. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`
   - Copy the generated URL, paste in browser, invite to your server
5. **General Information** → copy the **Application ID** and **Public Key**
6. `.env` entries:

```
DISCORD_TOKEN=           # from step 2
DISCORD_APPLICATION_ID=  # from step 5
DISCORD_PUBLIC_KEY=      # from step 5
DISCORD_GUILD_ID=        # right-click your server → Copy Server ID
```

---

## 2. Google Calendar

### 2a. Create OAuth 2.0 Client ID

1. Go to [Google Cloud Console](https://console.cloud.google.com) → create or select a project
2. **APIs & Services → Library** → search "Google Calendar API" → **Enable**
3. **APIs & Services → OAuth consent screen**:
   - User Type: **External**
   - App name: "Discal" (or your choice)
   - User support email: your email
   - Developer email: your email
   - Scopes: none needed on this screen (the app requests them at runtime)
   - **Test users**: Add your Google account email here while in testing mode
   - **Save and Continue** → back to Dashboard
4. **APIs & Services → Credentials** → **Create Credentials** → **OAuth Client ID**
   - Application type: **Desktop app**
   - Name: "Discal Setup"
   - Download the JSON → save as `client-secret.json` in the project root

### 2b. Create the shared calendar

5. In the same project, **IAM & Admin → Service Accounts** → **Create Service Account**
   - Name: "discal-calendar-creator"
   - Skip the role/permission step (not needed for this one-time action)
6. Create a key for the service account (JSON) → save as `service-account.json` in the project root
7. Run this to create the shared calendar (run locally with Python 3.12+):

```bash
pip install google-api-python-client google-auth
python -c "
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_info(json.load(open('service-account.json')))
svc = build('calendar', 'v3', credentials=creds)
cal = svc.calendars().insert(body={'summary': 'Your Calendar Name'}).execute()
print('CALENDAR_ID=' + cal['id'])
"
```

8. Copy the `CALENDAR_ID` into `.env`:

```
GOOGLE_CALENDAR_ID=abc123...@group.calendar.google.com
```

9. Delete `service-account.json` (no longer needed — the bot uses OAuth)

### 2c. OAuth2 refresh token (enables attendee management)

10. Run the one-time setup script:

```bash
pip install google-auth-oauthlib
python scripts/setup_oauth.py
```

11. Your browser opens → authorize with the Google account added in step 3 (test users)
12. The script writes `GOOGLE_REFRESH_TOKEN` to `.env`
13. You can now publish the OAuth consent screen (optional — only if you want others to self-host)

### 2d. Verify `.env` is complete

```
GOOGLE_CLIENT_SECRET_FILE=./client-secret.json
GOOGLE_REFRESH_TOKEN=1//...
GOOGLE_CALENDAR_ID=abc123...@group.calendar.google.com
```

---

## 3. Server Setup

### Option A: DigitalOcean Droplet (recommended)

1. Create a droplet: Ubuntu 24.04, 512MB RAM ($4/mo), add your SSH key
2. Point your domain's A record to the droplet IP (e.g. `discal.yourdomain.com → 159.89.95.156`)
3. SSH in and install Docker:

```bash
curl -fsSL https://get.docker.com | sh
```

4. Clone the repo:

```bash
git clone https://github.com/stewdotorg/discord-calendar.git /opt/discal
cd /opt/discal
```

5. Copy your files to the server:

```bash
# From your local machine:
scp .env client-secret.json root@YOUR_DROPLET_IP:/opt/discal/
```

6. Edit the Caddyfile with your domain:

```
yourdomain.com {
    reverse_proxy bot:8000
}
```

7. Start:

```bash
docker compose up -d --build
```

### Option B: Any Docker host

Same as above, but replace Caddy with your own reverse proxy. Bot listens on port 8000 (configurable via `HOST`/`PORT` in `.env`). The `/health` endpoint returns 200 for health checks.

### Option C: Local development

```bash
# Install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
DISCORD_GUILD_ID=your_server_id python -m src.bot
```

The bot uses Discord's gateway (WebSocket) — no inbound HTTP needed. No tunnel required for slash commands during local dev.

---

## 4. Verify

1. Check logs: `docker compose logs bot -f`
2. Look for: `Calendar connected: {name}` (confirms OAuth token works)
3. In Discord, type `/cal ping` → should respond "pong"
4. Type `/cal create title:"Test event" when:"tomorrow 3pm"` → check Google Calendar

---

## 5. Maintenance

- **Redeploy after code changes:** `git pull && docker compose up -d --build`
- **Refresh token expiry:** OAuth refresh tokens don't expire unless revoked. If revoked, re-run `scripts/setup_oauth.py`
- **Database:** stored in Docker volume `bot_data` at `/app/data/discal.db`. Back it up with:
  ```bash
  docker compose cp bot:/app/data/discal.db ./backup.db
  ```
- **View logs:** `docker compose logs bot --tail=50`

---

## Architecture Notes

| Component | What |
|---|---|
| Discord connection | Gateway WebSocket (not HTTP interactions endpoint) |
| Google Calendar auth | OAuth2 user credentials with refresh token |
| Timezone | UTC everywhere internally; displayed in US Eastern |
| Event selection | Discord autocomplete from live Calendar API list |
| NLP dates | dateparser with timezone-aware UTC context |
| Tests | pytest + vcrpy for Google Calendar API integration tests |
| Reverse proxy | Caddy with auto Let's Encrypt TLS |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: google_auth_oauthlib` during setup | `pip install google-auth-oauthlib` |
| `accessNotConfigured` error in logs | Enable Calendar API in the project where OAuth client lives |
| `forbiddenForServiceAccounts` | You're using service account auth → switch to OAuth2 (this guide) |
| Bot doesn't respond to slash commands | Bot must be invited with `applications.commands` scope; wait 1 hour for Discord to sync |
| "Calendar not configured" | Check `GOOGLE_CALENDAR_ID` and credentials in `.env` |
| Docker memory exhaustion (OOM) on 512MB droplet | `docker system prune -af --volumes` periodically |
| Refresh token invalid after Google password reset | Re-run `scripts/setup_oauth.py` |
