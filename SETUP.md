# Discal — Setup Guide

How to stand up your own Discal: one Discord server, one shared Google
Calendar, one bot. See the [README](README.md#how-it-works) for how the pieces
fit together.

**You need:** a Discord application, a Google account for the bot, a Google
Cloud project, and a Docker host (a 512 MB VPS is enough).

---

## 1. Discord application

1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** (e.g. "Discal").
2. **Bot** tab → **Reset Token** → copy it.
3. **Bot** tab → **Privileged Gateway Intents** → enable **Message Content Intent**.
   The bot needs it to read users' DM replies when it asks for their email.
   Without it those replies are silently ignored.
4. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `Send Messages`, `Use Slash Commands`
   - Open the generated URL and invite the bot to your server.
5. **General Information** → copy the **Application ID** and **Public Key**.

```
DISCORD_TOKEN=                    # step 2
DISCORD_APPLICATION_ID=           # step 5
DISCORD_PUBLIC_KEY=               # step 5
DISCORD_GUILD_ID=                 # right-click your server → Copy Server ID (Developer Mode)
DISCORD_ENABLE_MESSAGE_CONTENT=true
```

The bot serves exactly one server. Commands are registered to that guild only.

---

## 2. Google: the bot's account and the shared calendar

The bot acts as **one Google account**. All events live on **one shared
calendar** that account can edit. Invitees just get Google invitation emails.
The bot never gets access to their calendars.

### 2a. Choose the bot's Google account

Use a dedicated Google account (recommended) or your own. Whatever account
you authorize in step 2d is the identity the bot uses for every command. It
will show up as the event organizer.

### 2b. Create the shared calendar

Signed in as the bot's account, open Google Calendar → **Other calendars → +
→ Create new calendar**. Then open its **Settings → Integrate calendar** and
copy the **Calendar ID** (ends in `@group.calendar.google.com`).

To use an existing calendar instead, share it with the bot's account using
**Make changes to events**.

```
GOOGLE_CALENDAR_ID=abc123...@group.calendar.google.com
```

### 2c. Create an OAuth client

1. [Google Cloud Console](https://console.cloud.google.com) → create or select a project.
2. **APIs & Services → Library** → **Google Calendar API** → **Enable**.
3. **APIs & Services → OAuth consent screen**: User type **External**, fill in app name and emails.
   - Add the bot's Google account under **Test users**.
   - **Publish the app (set it to Production)** once it works. While the app is in
     *Testing*, Google expires the refresh token after **7 days** and the bot
     starts logging `invalid_grant`. An unverified app in Production works for
     up to 100 users. You'll click through an "unverified app" warning when you
     authorize.
4. **APIs & Services → Credentials → Create Credentials → OAuth Client ID** → type **Desktop app**.
   Download the JSON and save it as `client-secret.json` in the project root.

### 2d. Authorize the bot's account

```bash
python scripts/setup_oauth.py
```

A browser opens. Sign in as the **bot's account** and approve. The script
writes `GOOGLE_REFRESH_TOKEN` to `.env`.

```
GOOGLE_CLIENT_SECRET_FILE=./client-secret.json
GOOGLE_REFRESH_TOKEN=1//...
GOOGLE_CALENDAR_ID=abc123...@group.calendar.google.com
```

---

## 3. Run it

### Local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values from steps 1–2
python -m src.bot
```

The bot connects out to Discord's gateway over WebSocket. It needs no
inbound port, tunnel or domain.

### VPS (Docker Compose)

```bash
# On the server (Ubuntu + Docker: curl -fsSL https://get.docker.com | sh)
git clone https://github.com/stewdotorg/discord-calendar.git /opt/discal

# From your machine: secrets are not in git
scp .env client-secret.json root@YOUR_SERVER:/opt/discal/

# On the server
cd /opt/discal && docker compose up -d --build
```

`client-secret.json` is copied into the image at build time, so rebuild
(`--build`) if it changes.

On a 512 MB droplet, add swap (e.g. a 1 GiB swapfile). The compose file caps the
bot at 256 MB, so a leak restarts the container instead of exhausting the host.

---

## 4. Verify

1. `docker compose logs bot --tail=50` should show `Calendar connected: <name>`
   and `Ready`. It should **not** say `message_content intent disabled`.
2. In Discord: `/cal ping` → "pong".
3. `/cal create title:"Test" when:"tomorrow 3pm"` → the event appears on the shared calendar.

---

## 5. Maintenance

| Task | How |
|---|---|
| Deploy code changes | `git pull && docker compose up -d --build` |
| Apply `.env` changes | `docker compose up -d --force-recreate` (`restart` keeps the old env) |
| Logs | `docker compose logs bot --tail=50` |
| Back up the DB | `docker compose cp bot:/app/data/discal.db ./backup.db` (volume `bot_data`) |
| Free disk | `docker builder prune -af && docker image prune -af`. **Don't** add `--volumes`, which deletes the database volumes. |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `invalid_grant` in logs | Refresh token expired or was revoked. Publish the consent screen (step 2c), re-run `scripts/setup_oauth.py`, copy the new `.env` to the server, then `docker compose up -d --force-recreate`. |
| Users reply to the bot's email DM and nothing happens | Message Content intent is off. Enable it in the Developer Portal (step 1.3), set `DISCORD_ENABLE_MESSAGE_CONTENT=true`, recreate the container. |
| Bot fails to connect after enabling the env var | The intent isn't enabled in the Developer Portal. Enable it there first. |
| `accessNotConfigured` | Enable the Calendar API in the project that owns the OAuth client. |
| Slash commands missing or stale | Check the invite included `applications.commands`. Discord desktop caches command definitions, so if they still look stale, kick and re-invite the bot. |
| "Calendar not configured" | Check `GOOGLE_CALENDAR_ID` and the OAuth values in `.env`. |
