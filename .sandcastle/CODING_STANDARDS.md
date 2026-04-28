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
