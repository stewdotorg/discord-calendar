---
name: prepare-afk-feature
description: Interview user about a new feature, design vertical tracer-bullet issues with dependency DAG, create them on GitHub, present a plan with deep-module impact analysis. Use when user wants to design a feature for AFK implementation, says "prepare feature", "afk feature", or "new feature".
---

# Prepare AFK Feature

Interview the user about a new feature, break it into vertical tracer-bullet issues, and optionally implement it.

## Process

### 1. Gather feature requirements (focused interview)

**Interview style:**
- Number every question so the user can answer by reference (e.g. "re q3: …").
- Make questions multiple choice wherever possible.
- Recommend an answer when you have high confidence you're NOT missing critical information. If you ARE missing context, ask a drilling question first instead of guessing.
- Ask one question at a time. This is deeper than the bugfix interview — features need design decisions — but not as exhaustive as a full grill-me. Target 6-10 questions. Stop when the decision tree is complete.

1. **What's the feature?** One-sentence summary. What command or behavior does the user want?
2. **User story.** Who uses it, what do they type, what do they see? Give the exact Discord slash command if applicable.
3. **Scope boundaries.** What is explicitly OUT of scope for this feature? (Prevents scope creep in the AFK agent.)
4. **Which layers does it touch?** Discord command handler → Calendar API? Discord command handler → SQLite? Discord → Calendar → SQLite? Any new Google Calendar API surface?
5. **Does it need a new deep module method?** E.g., a new `CalendarService` method, a new `db/queries.py` function, or a new auth flow? Or is it pure wiring between existing methods?
6. **Dependencies on other features.** Does this depend on any unbuilt issues or open PRs? Is anything else blocked by this?
7. **Data model changes.** New SQLite tables? New columns? New `.env` variables?
8. **Error UX.** What does the user see when things go wrong? (Calendar API down, invalid input, missing config.)

### 2. Explore the codebase

Read the relevant existing code to understand what's already there. Prioritize in this order:

1. Existing command handlers in `src/commands/` — the new feature may parallel an existing one
2. Deep module interfaces in `src/calendar/service.py` and `src/db/queries.py` — what methods already exist that the feature can compose?
3. Existing tests in `tests/` — the test patterns to follow
4. Design decisions in `README.md` and `.agents/context/architecture.md` — don't violate them

### 3. Design vertical tracer-bullet issues

Break the feature into **tracer-bullet slices**. Each slice is a thin vertical cut through every layer (Discord → parsing → Calendar/DB) that delivers **demoable behavior on its own**. Never create horizontal slices (e.g., "add DB table for X" with no user-visible output).

**Issue structure for features:**

First issue is always the **skeleton**: the smallest possible end-to-end path that proves the feature works. This is the `/cal ping` equivalent — thin but complete.

Subsequent issues add depth: edge cases, options, polish, UX improvements.

**Label every issue `ready-for-agent`.**

**Define the dependency DAG.** Which issues can run in parallel? Which block others?

**Template for each issue:**

```
## What to build

[Concise description of this vertical slice. Describe end-to-end behavior,
not layer-by-layer implementation.]

## Acceptance criteria

- [ ] Criterion 1 (user-visible behavior)
- [ ] Criterion 2

## Affected deep modules

- `src/calendar/service.py` — [what new or existing methods are needed]
- `src/db/queries.py` — [what new or existing functions are needed]

## Files to touch

- [list specific files]

## Blocked by

- #<issue-number> — or "None — can start immediately"
```

### 4. Present the feature plan

Summarize for the user in a numbered list for ease of reference:

1. **Feature summary:** one-line what it does
2. **Issue breakdown:** numbered list with dependency graph shown as indented tree:
   ```
   #20: /cal search skeleton (unblocked)
   #21: /cal search filters (blocked by #20)
   #22: /cal search autocomplete (blocked by #20, parallel with #21)
   ```
3. **Deep module impact:** what new methods are needed on `CalendarService` or `db/queries.py`? Are existing method signatures changing? This is the highest-risk part — new deep module methods are fine, rewriting existing ones is dangerous. The agent should ADD methods, not refactor the module's interface.
4. **Shallow module impact:** which new command handler files? Which command groups get new subcommands?
5. **Test strategy:** is a new VCR cassette needed? Can early slices be pure mock while later slices hit VCR? Which tests need `.env` secrets?
6. **Post-implementation steps:** what needs human QA? Any VCR re-recording on the droplet? Any `.env` changes?

### 5. Create the issues

File each issue on GitHub in dependency order (blockers first), so you can reference real issue numbers in the `Blocked by` fields:

```bash
gh issue create --title "/cal search — find events by keyword" \
  --body "..." --label ready-for-agent
```

### 6. Offer to implement

Ask the user whether to implement now. If yes, work the issues in dependency
order, test-first, one small commit per logical change. Run `pytest` and
`ruff check src tests` before each commit.

### 7. Report back

Show the user in a numbered list:

1. Commits made and test results.
2. Whether a deploy or `.env` change is needed (see `.agents/context/deploying.md`).
3. Reminder: QA the feature in Discord after deploying. Re-record VCR cassettes if Calendar API calls changed.

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
