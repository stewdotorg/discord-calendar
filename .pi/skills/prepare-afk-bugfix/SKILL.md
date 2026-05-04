---
name: prepare-afk-bugfix
description: Interview user about a bug, create tracer-bullet GitHub issues, present a fix plan with deep-module impact analysis, and optionally dispatch the Sandcastle AFK factory. Use when user wants to prepare a bugfix for AFK implementation, file a bug for the agent to fix, or says "prepare bugfix", "afk bugfix", "file a bug for sandcastle".
---

# Prepare AFK Bugfix

Interview the user about a bug, create issues, and optionally dispatch the AFK factory.

## Process

### 1. Gather bug context (lightweight interview)

**Interview style:**
- Number every question so the user can answer by reference (e.g. "re q3: …").
- Make questions multiple choice wherever possible.
- Recommend an answer when you have high confidence you're NOT missing critical information. If you ARE missing context, ask a drilling question first instead of guessing.
- Ask one question at a time. Stop when the answer is already clear from context.
- Target 4-6 questions max — this is a bug, not a design review.

1. **What's the bug?** What command or behavior is broken? What's the observed vs expected output?
2. **Reproduction steps.** Exact inputs that trigger it. Include Discord command string if applicable.
3. **Scope.** Is this a crash (exception/stack trace), a wrong result, or a missing behavior?
4. **When did it break?** Recent deploy? After a specific Sandcastle run? Always been broken?
5. **Anything else the fixer needs to know?** Edge cases, affected users, urgency.

If the user provides a GitHub issue number, pull it: `gh issue view <number>`.

### 2. Explore the codebase

Read the files most likely involved based on the bug description. Prioritize in this order:

1. Command handler: `src/commands/<command>.py`
2. Calendar service: `src/calendar/service.py` (deep module — all Calendar API calls go through here)
3. Database: `src/db/queries.py` (deep module — all SQLite access)
4. Utilities: `src/utils.py`
5. Relevant tests: `tests/test_<module>.py`
6. Coding standards: `.sandcastle/CODING_STANDARDS.md`

Map the bug to the affected module interfaces. Identify which deep modules need changes vs which shallow modules (command handlers) just need wiring.

### 3. Create GitHub issues

Use the to-issues pattern to create issues:

**Always create these two issues:**

1. **Regression test** — a failing test that reproduces the bug (RED phase). This is the first commit the agent should make. Label: `ready-for-agent`, blocked by: none.
2. **Bugfix** — the implementation fix (GREEN + REFACTOR phases). Label: `ready-for-agent`, blocked by: the regression test issue.

If the bug spans multiple independent fixes, split accordingly. Each fix gets its own test + fix issue pair.

**Issue template:**

```
## Bug

[Concise description of the broken behavior]

## Reproduction

[Exact steps to reproduce]

## Expected

[What should happen]

## Actual

[What happens instead, including error messages]

## Affected modules

- `src/calendar/service.py` — [deep module: what API call is wrong?]
- `src/commands/create.py` — [command handler: what parameter handling is off?]
- etc.

## Files to touch

- [list specific files]
```

### 4. Present the fix plan

Summarize for the user in a numbered list for ease of reference:

1. **Root cause:** one-line diagnosis
2. **Deep module impact:** is `CalendarService` getting a new method? An existing method signature changing? Is `db/queries.py` involved? These are the high-risk changes — the agent needs to respect existing interfaces and add methods, not rewrite modules.
3. **Shallow module impact:** which command handlers need wiring changes? These are low-risk — just pass-through to the deep modules.
4. **Test strategy:** is a new VCR cassette needed? Can the test be pure mock? Will existing tests break?
5. **Estimated touches:** how many files, new lines of test vs implementation.

### 5. Offer dispatch

Ask the user:

> Ready to dispatch? This will run `npm run sandcastle` in `~/dev/discal`, which picks up the new `ready-for-agent` issues. The planner will schedule the regression test first, then the fix. Both run in isolated Docker sandboxes with TDD.

If the user says yes:

```bash
cd ~/dev/discal
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
npm run sandcastle
```

If Docker isn't running, warn the user. If the sandcastle image needs rebuilding, run `npx sandcastle docker build-image` first.

### 6. Report back

After dispatch, show the user in a numbered list:

1. The log file paths: `.sandcastle/logs/main-planner.log`, etc.
2. How to tail: `tail -f .sandcastle/logs/sandcastle-issue-*-implementer.log`
3. How to check status: `gh issue list --label ready-for-agent`
4. Reminder: QA the result when the factory finishes. Pull, run tests, test in Discord.

## Deep Modules Reference (Discal)

These are the modules the agent must not casually rewrite. Changes here are high-leverage:

| Module | File | Interface |
|---|---|---|
| CalendarService | `src/calendar/service.py` | Single entry point for ALL Google Calendar API. Methods: `verify_access`, `create_event`, `list_events`, `get_event`, `update_event`, `add_attendees`, `add_reminders`, `delete_event` |
| Database | `src/db/queries.py` | All SQLite access. Never access SQLite directly outside this module. |
| Auth | `src/calendar/auth.py` | OAuth2 credential loading and refresh. |
| Discord client | `src/bot.py` | Bot lifecycle (startup, shutdown, command sync). |

Shallow modules (safe for agents to freely modify):
- `src/commands/*.py` — command handlers (thin — parse args, call CalendarService, format response)
- `src/utils.py` — formatting, timezone, helpers
