# Deploying — Discal

How to deploy Discal to the DigitalOcean droplet and manage the dev container.

## Production

```bash
# From laptop — deploy/update prod
ssh discord-calendar-bot "cd /opt/discal && git pull && docker compose up -d --build"

# View prod logs
ssh discord-calendar-bot "cd /opt/discal && docker compose logs bot --tail=50"

# Prod uses .env, port 8000, volume bot_data
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
