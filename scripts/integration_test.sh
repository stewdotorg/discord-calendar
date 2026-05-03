#!/usr/bin/env bash
# =============================================================================
# Integration Test Gate — run on the droplet before QA handoff.
#
# Usage:
#   ./scripts/integration_test.sh           # Playback (fast, no credentials needed)
#   ./scripts/integration_test.sh --record  # Re-record VCR cassettes against live API
#
# What it does:
#   1. Lints with ruff
#   2. Runs the full test suite (unit + VCR integration)
#   3. If --record: records fresh cassettes, then replays to verify
#   4. Prints a pass/fail summary
#
# Designed to run on the droplet via docker compose:
#   docker compose run --rm bot bash scripts/integration_test.sh
#   docker compose run --rm bot bash scripts/integration_test.sh --record
#
# After --record, copy cassettes back to local for commit:
#   docker compose cp bot:/app/tests/cassettes/. ./tests/cassettes/
#   exit  # back to local
#   scp discord-calendar-bot:/opt/discal/tests/cassettes/test_*.yaml ./tests/cassettes/
#   git add tests/cassettes/ && git commit -m "test: record VCR cassettes"
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
START_TIME=$(date +%s)

log_section() {
    echo ""
    echo -e "${YELLOW}━━━ $1 ━━━${NC}"
}

log_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    PASS=$((PASS + 1))
}

log_fail() {
    echo -e "  ${RED}✗${NC} $1"
    FAIL=$((FAIL + 1))
}

# ── Parse flags ─────────────────────────────────────────────────────────────

RECORD=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --record) RECORD=true; shift ;;
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done

# ── 1. Ruff lint ─────────────────────────────────────────────────────────────

log_section "1. Lint (ruff)"
if ruff check src/ tests/ 2>&1; then
    log_pass "ruff clean"
else
    log_fail "ruff found issues"
fi

# ── 2. Unit + command tests (no credentials needed) ───────────────────────────

log_section "2. Unit & Command Tests"
# Exclude VCR tests — they get their own step.
# Run test files individually to avoid OOM on 512MB droplets.
UNIT_FAILED=0
for test_file in tests/test_bot.py tests/test_calendar.py tests/test_commands.py \
    tests/test_db.py tests/test_delete.py tests/test_edit.py \
    tests/test_reminders.py tests/test_rsvp.py; do
    if python -m pytest "$test_file" -v --tb=short 2>&1; then
        log_pass "$(basename "$test_file")"
    else
        log_fail "$(basename "$test_file")"
        UNIT_FAILED=1
    fi
done
# Large files split by class to avoid OOM on 512MB droplets
for batch in "tests/test_create.py -k 'not TestParseWhen'" \
             "tests/test_create.py -k TestParseWhen" \
             "tests/test_utils.py -k 'TestFormatDeleteError or TestGetTodayEasternRange or TestFormatTimeRangeEastern'" \
             "tests/test_utils.py -k 'TestFormatEventsEmbed or TestParseWhenDateparser or TestParseDateEastern'"; do
    if python -m pytest $batch -v --tb=short 2>&1; then
        log_pass "$(echo "$batch" | cut -d' ' -f1 | xargs basename) ($(echo "$batch" | grep -oP "(?<=-k ).*"))"
    else
        log_fail "$(echo "$batch" | cut -d' ' -f1 | xargs basename) ($(echo "$batch" | grep -oP "(?<=-k ).*"))"
        UNIT_FAILED=1
    fi
done
if [ "$UNIT_FAILED" -eq 0 ]; then
    log_pass "unit + command tests pass"
else
    log_fail "unit + command tests failed"
fi

# ── 3. VCR integration tests ─────────────────────────────────────────────────

if $RECORD; then
    log_section "3. VCR Recording (live Google Calendar API)"

    # Clean stale cassettes first
    rm -f tests/cassettes/test_*.yaml
    echo "  Stale cassettes removed."

    if python -m pytest tests/test_calendar_vcr.py -v \
        --record \
        --tb=long \
        2>&1; then
        log_pass "VCR recording pass"
    else
        log_fail "VCR recording failed"
    fi

    # ── 4. Verify playback from recorded cassettes ────────────────────────────

    log_section "4. VCR Playback Verification (offline, no network)"

    if python -m pytest tests/test_calendar_vcr.py -v \
        --tb=short \
        2>&1; then
        log_pass "VCR playback pass (cassettes are clean)"
    else
        log_fail "VCR playback failed (cassettes may be corrupt)"
    fi
else
    log_section "3. VCR Playback (offline, from committed cassettes)"

    if python -m pytest tests/test_calendar_vcr.py -v \
        --tb=short \
        2>&1; then
        log_pass "VCR playback pass"
    else
        log_fail "VCR playback failed"
    fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────

ELAPSED=$(($(date +%s) - START_TIME))

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Total: $((PASS + FAIL))  |  ${GREEN}Pass: $PASS${NC}  |  ${RED}Fail: $FAIL${NC}  |  ${ELAPSED}s"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo -e "${RED}INTEGRATION GATE FAILED — do not hand off to QA.${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}INTEGRATION GATE PASSED — ready for QA.${NC}"
    exit 0
fi
