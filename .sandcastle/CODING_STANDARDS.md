# Coding Standards — Discal

Customize this file with your project's coding standards.
The reviewer agent loads it during code review via @.sandcastle/CODING_STANDARDS.md
so these standards are enforced during review without costing tokens during implementation.

## Style

- Follow PEP 8. Use `ruff` for linting and formatting.
- Use `snake_case` for variables, functions, and methods.
- Use `PascalCase` for classes.
- Use `UPPER_CASE` for module-level constants.
- Type hints on all public function signatures (parameters and return types).
- Use `str | None` not `Optional[str]` (Python 3.10+ union syntax).
- Use `list[str]` not `List[str]` (built-in generics, no `from typing import List`).
- Docstrings: Google-style with Args, Returns, Raises sections.
- Max line length: 100 characters.
- Imports: standard library first, then third-party, then local. One import per line.

## Testing

- Use `pytest` as the test runner.
- Every public function in `calendar/service.py` must have at least one test.
- Every Discord command handler must have at least one integration test.
- Use descriptive test names: `test_create_event_returns_event_id`.
- Mock at system boundaries only: Discord HTTP interactions, Google Calendar API.
- Never mock internal collaborators (other project modules).
- Tests live in `tests/` mirroring the `src/` structure.
- Use `pytest fixtures` for shared setup (e.g., mock calendar client).
- Run tests with: `python -m pytest tests/ -v`

### Integration Testing with VCR

This project uses **VCR (vcrpy)** for integration tests against the real Google Calendar API.
VCR records HTTP interactions to cassette files (`tests/cassettes/`) so tests can replay
without network access — providing the fidelity of live API testing with the speed and
repeatability of offline fixtures.

**Two modes:**

| Mode | Command | Behavior |
|---|---|---|
| **Playback** (default) | `pytest tests/test_calendar_vcr.py` | Replays cassettes. No network. No credentials needed. |
| **Record** | `pytest tests/test_calendar_vcr.py --record` | Hits live Google API. Re-records all cassettes. Requires `.env` with credentials. |

**When to record cassettes:**
- After adding new VCR tests
- After changing API request bodies (e.g., new event fields)
- After OAuth token rotation
- After calendar schema changes

**When cassettes suffice (no re-record needed):**
- Refactoring code without changing API calls
- Running existing VCR tests in CI or sandbox (no credentials available)
- Pre-commit validation

**Cassette hygiene:**
- Use `_unique_title(suffix)` for deterministic event titles — never `uuid4()` or timestamps.
  Deterministic titles let VCR match recorded request bodies at playback time.
- Delete stale cassettes before re-recording: `rm tests/cassettes/test_*.yaml`
- Commitment: recorded cassettes are committed to git as offline test fixtures.
- Authorization headers are automatically stripped before recording (see `conftest.py`).
- Each distinct API call gets its own named cassette: `with vcr.use_cassette("test_name"):`

**Recording workflow:**
```bash
# 1. On the droplet (has .env + client-secret.json):
ssh discord-calendar-bot
cd /opt/discal
docker compose run --rm bot bash scripts/integration_test.sh --record
# Gate passes → copy cassettes out of container:
docker compose cp bot:/app/tests/cassettes/. ./tests/cassettes/
exit

# 2. Back on local — pull cassettes from droplet and commit:
scp discord-calendar-bot:/opt/discal/tests/cassettes/test_*.yaml ./tests/cassettes/
git add tests/cassettes/ && git commit -m "test: record VCR cassettes" && git push
```

**Sandcastle limitations:** Docker sandboxes have no `.env` secrets — VCR tests in sandcastle
run in playback mode only. Record cassettes manually on the droplet before/after sandcastle runs
that touch Calendar API code.

### Integration Test Gate (Pre-QA)

Before handing off to human QA, run the integration test gate on the droplet:

```bash
# Quick gate using committed cassettes (do this for non-API changes):
ssh discord-calendar-bot "cd /opt/discal && docker compose run --rm bot bash scripts/integration_test.sh"

# Full gate with fresh cassette recording (do this when API code changed):
ssh discord-calendar-bot "cd /opt/discal && docker compose run --rm bot bash scripts/integration_test.sh --record"
# Then pull cassettes back to local for commit:
ssh discord-calendar-bot "cd /opt/discal && docker compose cp bot:/app/tests/cassettes/. ./tests/cassettes/"
scp discord-calendar-bot:/opt/discal/tests/cassettes/test_*.yaml ./tests/cassettes/
git add tests/cassettes/ && git commit -m "test: record VCR cassettes" && git push
```

The gate runs, in order:
1. **ruff lint** — checks style and static analysis
2. **Unit + command tests** — all tests except VCR (no credentials needed)
3. **VCR tests** — integration tests against Google Calendar API (record or playback)
4. **VCR playback verification** — only with `--record`: replays recorded cassettes to confirm they're clean

If the gate fails, **do not hand off to QA**. Fix issues and re-run.

## Architecture

- Deep modules: small public interface, deep implementation. Fewer methods = better.
- Accept dependencies, don't create them. Pass services into constructors.
- Return results, don't produce side effects.
- `calendar/service.py` is the single entry point for all Google Calendar operations.
- Settings persistence goes through `db/queries.py` — never access SQLite directly outside `db/`.
- Discord command handlers live in `src/commands/` — one module per command group.
- Shared utilities (autocomplete, embed formatting, timezone) go in `src/utils.py`.

## Code Quality

- Check with `ruff check src/ tests/` before committing.
- No `print()` in production code. Use `logging` module.
- No bare `except:`. Catch specific exceptions.
- Handle Google Calendar API errors with specific user-facing messages.
- Use `from __future__ import annotations` for forward references when needed.
- Prefer `dataclasses` for data containers.
- Prefer `def` + early returns over deeply nested `if` blocks.
