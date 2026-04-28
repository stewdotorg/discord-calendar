# Discal — Pocock/Sandcastle Workflow

## Checklist

### Phase 1: Alignment (Human-in-the-Loop)

- [ ] Run Grill Me skill — interview relentlessly about every design decision
- [ ] Resolve: Discord commands (slash vs. prefix, subcommands)
- [ ] Resolve: Google Calendar operations (create, read, update, delete, list, free/busy, recurring)
- [ ] Resolve: Auth model (service account vs. per-user OAuth)
- [ ] Resolve: Single-guild vs. multi-guild, per-guild calendar config
- [ ] Resolve: Error UX (what does user see when Calendar API is down?)
- [ ] Resolve: Timezone handling, natural language date parsing
- [ ] Resolve: Deployment target, hosting, domain/SSL for Interactions Endpoint

### Phase 2: PRD → Kanban Board

- [ ] Write PRD capturing decisions from Grill Me session
- [ ] Break PRD into vertical tracer bullets (each touches Discord → parsing → Calendar)
- [ ] Define dependency DAG between issues
- [ ] File each issue on GitHub, label `ready-for-agent`
- [ ] Recommended first tick: `/cal ping` → `"pong"` (proves end-to-end connectivity)

### Phase 3: Codebase Setup & Architecture

- [ ] Initialize repo with chosen stack (TypeScript, discord.js, googleapis)
- [ ] Run `sandcastle init` — choose Docker, Claude Code, `parallel-planner-with-review` template
- [ ] Customize Dockerfile (Node, bot dependencies, googleapis)
- [ ] Write `.sandcastle/CODING_STANDARDS.md`
- [ ] Design module interfaces (discord/commands.ts, calendar/service.ts, commands/*.ts)
- [ ] Stub interface files — AI fills in implementations

### Phase 4: Night Shift (AFK — Sandcastle)

- [ ] Review kanban board, verify issue dependencies
- [ ] Kick off `run.ts` (Planner → Implementers → Reviewers → Merger loop)
- [ ] Planner (Opus): reads `ready-for-agent` issues, builds dependency graph, picks unblocked
- [ ] Implementers (parallel, max 4): TDD each issue in isolated Docker sandboxes
- [ ] Reviewers (Opus): diff against main, apply coding standards, clean up
- [ ] Merger (Opus): merge branches, resolve conflicts, run full test suite, close issues
- [ ] Loop until no `ready-for-agent` issues remain

### Phase 5: Human QA (Impose Taste)

- [ ] Pull merged branch, manually test all commands in test guild
- [ ] Test: `/cal create`, `/cal today`, `/cal delete`, edge cases
- [ ] Test: missing arguments, invalid dates, auth failures, rate limits
- [ ] File new `ready-for-agent` issues for any gaps found
- [ ] Repeat Night Shift for any follow-up issues

---

## The Pocock/Sandcastle Workflow for Discal

Pocock would attack this in five phases, with Sandcastle handling Phase 4 entirely AFK. Here's the full blueprint:

---

### Phase 1: Grill Me (Human-in-the-Loop)

Run the **Grill Me skill** against the idea. The AI relentlessly interviews you, question by question, walking every branch of the design tree before a single line of code:

- What Discord commands? Slash or prefix? Subcommands?
- Which Google Calendar operations? Create, read, update, delete, list? Free/busy? Recurring events?
- Single guild or multi-guild? Per-guild calendar config?
- Auth model? Service account or per-user OAuth?
- What's the error UX — if Calendar API is down, what does the user see?
- Timezone handling? Natural language date parsing ("next tuesday")?

This produces **alignment** (shared understanding), not a document. The PRD that follows is just a write-up of what you already agree on — Pocock doesn't even read it.

---

### Phase 2: Alignment → PRD → Kanban Board

The PRD gets broken into a **kanban board of vertical tracer bullets**. Vertical means each issue touches every layer (Discord → parsing → Calendar API) and produces user-visible behavior. Horizontal (DB first, then API, then bot) is forbidden — AI defaults to horizontal, you must force vertical.

A candidate board with dependency DAG:

```
Tick 1: [Issue #1] /cal ping → "pong"    ←  no dependencies, proves Discord connectivity end-to-end
           |
Tick 2: [Issue #2] Google Calendar auth    ←  depends on #1 (need bot running to test auth flow)
           |
Tick 3: [Issue #3] /cal create "title" friday 2pm → event appears  ←  depends on #2
        [Issue #4] /cal today → lists today's events               ←  depends on #2
        [Issue #5] /cal delete <id> → removes event                 ←  depends on #3 (need events to delete)
           |
Tick 4: [Issue #6] Natural language date parsing     ←  depends on #3
        [Issue #7] Multi-guild / per-guild calendars  ←  depends on #2
```

Each labeled `ready-for-agent` on GitHub. The DAG lets Sandcastle parallelize unblocked issues.

---

### Phase 3: Codebase Setup & Architecture

Before the night shift, you lay the foundation:

1. **`sandcastle init`** in the repo — chooses Docker, Claude Code, and the `parallel-planner-with-review` template
2. **Dockerfile** includes Node, discord.js, googleapis, the bot runtime
3. **`.sandcastle/CODING_STANDARDS.md`** defines the rules agents must follow (pushed to reviewer, pulled by implementer)
4. **Module interfaces designed by you**, implementations delegated to AI:

```
src/
  discord/
    commands.ts      ← interface: registerSlashCommand(), handleInteraction()
    bot.ts           ← "deep module": start/stop behind small interface
  calendar/
    service.ts       ← interface: createEvent(), listEvents(), deleteEvent()
    auth.ts          ← OAuth flow, token refresh
  commands/
    create.ts        ← implements Discord → Calendar pipeline for /cal create
    list.ts          ← /cal today, /cal week
    delete.ts        ← /cal delete
  index.ts           ← wires everything, exports startBot()
```

You design the **interfaces** (`createEvent(params: CreateEventParams): Promise<Event>`). AI fills in the **implementations**. This is the "gray box" model — you know the shape, you don't need to read every line inside.

---

### Phase 4: Night Shift (Sandcastle AFK)

This is where you walk away. `run.ts` executes a loop:

```
┌─────────────────────────────────────────────────────┐
│ while issues remain:                                 │
│                                                      │
│   [Planner]  Opus reads all ready-for-agent issues   │
│              Builds dependency graph                 │
│              Outputs unblocked issues as <plan> JSON │
│                                                      │
│   [Implementers]  Parallel, max 4, Docker sandboxes  │
│     Issue #3 → worktree → sandbox → Opus            │
│       TDD: write failing test → implement → refactor │
│       typecheck → test → commit "RALPH: ..."         │
│       output <promise>COMPLETE</promise>             │
│                                                      │
│     Issue #4 → worktree → sandbox → Opus (parallel)  │
│       Same TDD cycle                                 │
│                                                      │
│   [Reviewers]  Same worktrees, fresh Opus contexts   │
│     Diff against main, apply CODING_STANDARDS.md     │
│     Clean up naming, reduce nesting, remove cruft    │
│     Preserve functionality, run tests again          │
│                                                      │
│   [Merger]  Single Opus agent                        │
│     git merge each branch, resolve conflicts         │
│     Full test suite → commit → close GitHub issues   │
│                                                      │
│   Loop ← issues still open? Planner re-evaluates     │
└─────────────────────────────────────────────────────┘
```

Each implementer gets a **fresh context window** (smart zone). Each runs inside its own **git worktree mounted into Docker** — fully isolated, can't step on each other. TDD is non-negotiable: the implement-prompt explicitly requires RED → GREEN → REFACTOR cycles.

Pocock uses **Opus for planning, implementation, and reviewing** (it needs the "smarts") but notes Sonnet is fine for implementation work.

The merge prompt closes the GitHub issues, completing the feedback loop.

---

### Phase 5: Human QA (Impose Taste)

Morning after night shift: you pull the merged branch and manually test. This is where you "impose your taste" — Pocock's phrase. Automated implementation without human QA produces "slop" (functional but soulless).

- Run the bot in a test guild
- Try `/cal create`, `/cal today`, `/cal delete`
- Check edge cases: missing arguments, invalid dates, auth failures
- File new `ready-for-agent` issues for anything that's off

---

### What This Means for You Practically

| What you do | What Sandcastle does |
|---|---|
| Grill Me interview | — |
| Write GitHub issues as vertical slices | — |
| Design module interfaces | — |
| `sandcastle init` + configure Dockerfile | — |
| Review the kanban board | Planner picks unblocked issues |
| Sleep / do other work | Implementers TDD each issue in parallel sandboxes |
| | Reviewers clean up code |
| | Merger consolidates branches |
| QA the merged result | — |

The key insight: **the code isn't an asset you produce, it's a battleground you shape throughout the process.** You never lose touch with it — you design the interfaces, you QA the output, you impose taste. But you don't write the implementation line by line.

For Discal specifically, this means maybe 6-8 well-scoped GitHub issues, a two-tick dependency DAG, and two night-shift runs — one to build the skeleton (auth + ping + create), one to flesh out the rest (list, delete, natural language parsing).
