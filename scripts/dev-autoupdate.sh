#!/bin/bash
# dev-autoupdate.sh — Pull latest main and rebuild dev container if main advanced.
#
# Fetches origin/main, then rebuilds the dev bot container only when
# main has new commits.  This is cheap when nothing changed (git fetch
# + git diff only).  Polls every 2 minutes via cron.
#
# Logs rebuild events to /var/log/dev-autoupdate.log.

set -euo pipefail

COMPOSE_FILE="/opt/discal/docker-compose.dev.yml"
SERVICE="bot-dev"
LOG_FILE="/var/log/dev-autoupdate.log"
export COMPOSE_PROFILES=dev

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $*" >> "$LOG_FILE"
}

cd /opt/discal || { log "ERROR: /opt/discal not found"; exit 1; }

# Fetch latest from origin
git fetch origin main 2>/dev/null || { log "ERROR: git fetch failed"; exit 1; }

# Check if main has advanced
if git diff --quiet main origin/main; then
    # No changes — nothing to do
    exit 0
fi

log "main has new commits — pulling and rebuilding dev container"

# Pull latest main
git pull origin main 2>/dev/null || { log "ERROR: git pull failed"; exit 1; }

# Rebuild and restart the dev container
docker compose -f "$COMPOSE_FILE" up -d --build "$SERVICE" 2>/dev/null || {
    log "ERROR: docker compose up failed"
    exit 1
}

log "dev rebuilt successfully — main updated"
