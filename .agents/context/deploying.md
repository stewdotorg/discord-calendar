# Deploying — Discal

How to deploy Discal to the DigitalOcean droplet and manage the dev container.

## Environments

| Env | Env file | Compose file | Container | Port |
|---|---|---|---|---|
| Prod | `.env` (current bot; will rename to `.env.prod`) | `docker-compose.yml` | `bot` | 8000 |
| Dev | `.env.dev` | `docker-compose.dev.yml` | `bot-dev` | 8001 |

## Pre-deploy smoke test

```bash
cd ~/dev/discal && source .venv/bin/activate && pytest tests/test_bot_setup.py -v
```

## Production

```bash
# From laptop — deploy/update prod
ssh discord-calendar-bot "cd /opt/discal && git pull && docker compose up -d --build"

# View prod logs
ssh discord-calendar-bot "cd /opt/discal && docker compose logs bot --tail=50"

# Quick restart (prod-only)
ssh discord-calendar-bot "docker restart discal-bot-1"

# Free disk space
ssh discord-calendar-bot "docker system prune -af --volumes"
```

## Dev Container

A side-by-side dev bot runs alongside prod with its own Discord application, database,
and port — completely isolated. Cron jobs auto-shutdown idle dev and auto-update
when `main` advances on GitHub.

### Startup

```bash
# Start dev (from laptop)
ssh discord-calendar-bot "cd /opt/discal && git pull && docker compose -f docker-compose.dev.yml up -d --build bot-dev"
```

### Status

```bash
# Check dev status
ssh discord-calendar-bot "cd /opt/discal && docker compose -f docker-compose.dev.yml ps"
```

### Auto-shutdown

Cron runs `scripts/dev-autoshutdown.sh` every 5 minutes. It checks the last log
timestamp of the dev container. If no log output in 30 minutes, the container is
stopped to free droplet memory. Log: `/var/log/dev-autoshutdown.log`.

### Auto-update

Cron runs `scripts/dev-autoupdate.sh` every 2 minutes. It fetches `main` from
GitHub and rebuilds the dev container only if `main` has new commits. This is
cheap when nothing changed (only `git fetch` + `git diff`). Log: `/var/log/dev-autoupdate.log`.

### Cron Entries

These run on the droplet (add via `crontab -e`):

```
*/2 * * * * /opt/discal/scripts/dev-autoupdate.sh
*/5 * * * * /opt/discal/scripts/dev-autoshutdown.sh
```

### Isolation

| Resource | Prod | Dev |
|---|---|---|
| Compose file | `docker-compose.yml` | `docker-compose.dev.yml` |
| Env file | `.env` | `.env.dev` |
| Port (host) | 8000 | 8001 |
| Database volume | `bot_data` | `bot_dev_data` |
| Profile | (none) | `dev` |

Dev uses `profiles: [dev]` — bare `docker compose up` ignores it.

## Gotchas

### `.env` changes require recreate, not restart
`docker compose restart` reuses the existing container's environment variables. After changing `.env`, use `docker compose up -d --force-recreate` (or `up -d --build` for code changes).

### `client-secret.json` is baked into the Docker image
The Dockerfile `COPY`s it at build time — it is NOT volume-mounted (unlike `service-account.json`). If `client-secret.json` changes, rebuild with `--build`.

### OAuth refresh token expires every 7 days (Testing status)
Google OAuth refresh tokens for apps in **Testing** publishing status expire after 7 days.
To fix permanently, set the OAuth consent screen to **Production** (no verification needed
for ≤100 users), then re-run setup_oauth.py.

When the bot logs `invalid_grant`, the refresh token expired. Fix:
```bash
cd ~/dev/discal && source .venv/bin/activate && python scripts/setup_oauth.py
scp .env discord-calendar-bot:/opt/discal/
ssh discord-calendar-bot "cd /opt/discal && docker compose up -d --force-recreate"
```

### Droplet unreachable but still running
If SSH times out but `doctl compute droplet list` shows the droplet as `active`,
it may be a transient network issue. Retry SSH. `doctl` can also power-cycle:
```bash
doctl compute droplet-action power-cycle 567799719
```

### Orphan dev container warning on prod up
Bare `docker compose up` shows `Found orphan containers ([discal-bot-dev-1])` —
harmless. The dev container uses a separate compose file (`docker-compose.dev.yml`).

### Commands not appearing in Discord
Discord desktop aggressively caches slash command schemas. Workaround: kick the bot from the guild and re-invite. Invite URL uses the app ID from `.env` — the bot can only be in one guild at a time (guild-only mode).
