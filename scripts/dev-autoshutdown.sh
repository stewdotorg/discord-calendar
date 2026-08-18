#!/bin/bash
# dev-autoshutdown.sh — Stop the dev bot container if idle for 30+ minutes.
#
# Checks the last log timestamp of the bot-dev container.  If the most recent
# log entry is older than 30 minutes, the dev container is stopped to free
# resources on the droplet.
#
# Logs shutdown events to /var/log/dev-autoshutdown.log.

set -euo pipefail

COMPOSE_FILE="/opt/discal/docker-compose.dev.yml"
SERVICE="bot-dev"
IDLE_MINUTES=30
LOG_FILE="/var/log/dev-autoshutdown.log"
export COMPOSE_PROFILES=dev

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $*" >> "$LOG_FILE"
}

stop_dev() {
    local reason="$1"
    log "$reason — stopping idle dev container"
    docker compose -f "$COMPOSE_FILE" stop "$SERVICE"
}

cd /opt/discal || { log "ERROR: /opt/discal not found"; exit 1; }

# Check if the dev container is running
if ! docker compose -f "$COMPOSE_FILE" ps "$SERVICE" --status running 2>/dev/null | grep -q "$SERVICE"; then
    exit 0
fi

# Get the last log line with timestamp
LAST_LOG=$(docker compose -f "$COMPOSE_FILE" logs "$SERVICE" --tail 1 --timestamps 2>/dev/null || true)

if [ -z "$LAST_LOG" ]; then
    stop_dev "No log output from $SERVICE"
    exit 0
fi

# Extract the timestamp (Docker format: 2026-05-23T12:34:56.789012345Z ...)
TIMESTAMP_STR=$(echo "$LAST_LOG" | awk '{print $2}' | sed 's/\.[0-9]*Z/Z/')
if [ -z "$TIMESTAMP_STR" ]; then
    stop_dev "Could not parse timestamp from $SERVICE"
    exit 0
fi

# Convert to epoch seconds
if date --version >/dev/null 2>&1; then
    # GNU date
    LAST_EPOCH=$(date -d "$TIMESTAMP_STR" +%s 2>/dev/null || echo 0)
else
    # BSD date (macOS)
    LAST_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$TIMESTAMP_STR" +%s 2>/dev/null || echo 0)
fi

NOW_EPOCH=$(date +%s)
DIFF_MINUTES=$(( (NOW_EPOCH - LAST_EPOCH) / 60 ))

if [ "$DIFF_MINUTES" -ge "$IDLE_MINUTES" ]; then
    stop_dev "Dev container idle for ${DIFF_MINUTES}m (≥${IDLE_MINUTES}m)"
else
    log "Dev container active (last log ${DIFF_MINUTES}m ago) — leaving running"
fi
