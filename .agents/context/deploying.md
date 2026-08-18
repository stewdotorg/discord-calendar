# Deploying — Discal

How to deploy Discal to the DigitalOcean droplet and manage the dev container.

## Environments

| Env | Env file | Compose file | Container |
|---|---|---|---|
| Prod | `.env` (current bot; will rename to `.env.prod`) | `docker-compose.yml` | `bot` |
| Dev | `.env.dev` | `docker-compose.dev.yml` | `bot-dev` |

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

# Free disk space (build cache + unused images)
# NOTE: do NOT use `--volumes` — it deletes the dev DB (discal_bot_dev_data)
ssh discord-calendar-bot "docker builder prune -af && docker image prune -af"
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

Installed in root's crontab (verify with `crontab -l`):

```
*/2 * * * * /opt/discal/scripts/dev-autoupdate.sh
*/5 * * * * /opt/discal/scripts/dev-autoshutdown.sh
```

Both scripts `export COMPOSE_PROFILES=dev` — the dev service is profile-gated, so
without it every `docker compose` call in the script is a silent no-op.

### Isolation

| Resource | Prod | Dev |
|---|---|---|
| Compose file | `docker-compose.yml` | `docker-compose.dev.yml` |
| Env file | `.env` | `.env.dev` |
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
`docker compose up --remove-orphans` (prod file) will actually **remove** the dev
container — it's an orphan from the prod compose file's perspective.

### Commands not appearing in Discord
Discord desktop aggressively caches slash command schemas. Workaround: kick the bot from the guild and re-invite. Invite URL uses the app ID from `.env` — the bot can only be in one guild at a time (guild-only mode).

### Bot down with "Exited (137)" that won't restart (host OOM wedge)
If the prod container is `Exited (137)` and won't restart despite `unless-stopped`,
the host OOM-killer killed PID 1 and Docker's restart got wedged. Confirm in dockerd logs:
```bash
sudo journalctl -u docker | grep -i "restartmanger wait error"
# "failed to create task for container: AlreadyExists: task ... already exists"
```
Fix — remove the wedged container record (the data volume is untouched) and recreate:
```bash
ssh discord-calendar-bot "docker rm discal-bot-1 && cd /opt/discal && docker compose up -d"
```
Root cause is memory pressure — see the mitigations below.

### Memory protections (2026-08, don't undo)
The 512 MB droplet was chronically OOM. In place now:
- 1 GiB swapfile at `/swapfile` (persisted in `/etc/fstab`; `vm.swappiness=10` via `/etc/sysctl.d/99-swappiness.conf`).
- `mem_limit: 256m` on `bot` and `bot-dev` (compose files) — a leak now cgroup-kills and cleanly restarts instead of host-OOM-killing the droplet.
- journald capped: `/etc/systemd/journald.conf.d/99-discal.conf` (`SystemMaxUse=50M`, `RuntimeMaxUse=16M`).
- Disabled/masked unneeded services: `multipathd` (+`.socket`), `ModemManager`, `udisks2`, `packagekit` (masked), `fwupd` (masked), `fwupd-refresh.timer`.

### Dev autoshutdown idle math
`docker compose logs --timestamps` emits `<name>  | <RFC3339-ts> <msg>` — the timestamp
is awk field **3** (field 2 is the `|`). If the script ever logs "idle for <huge>m"
it means the field index regressed; check `awk '{print $3}'` in `dev-autoshutdown.sh`.
