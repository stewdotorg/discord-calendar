# TASK

Fix issue {{TASK_ID}}: {{ISSUE_TITLE}}

Pull in the issue using `gh issue view {{TASK_ID}}`. If it has a parent PRD, pull that in too.

Only work on the issue specified.

Work on branch {{BRANCH}}. Make commits and run tests.

# CONTEXT

Here are the last 10 commits:

<recent-commits>

!`git log -n 10 --format="%H%n%ad%n%B---" --date=short`

</recent-commits>

# EXPLORATION

Explore the repo and fill your context window with relevant information that will allow you to complete the task.

Pay extra attention to test files that touch the relevant parts of the code.

# EXECUTION

If applicable, use RGR to complete the task.

1. RED: write one test
2. GREEN: write the implementation to pass that test
3. REPEAT until done
4. REFACTOR the code

# FEEDBACK LOOPS

Before committing, run `ruff check src/ tests/` for linting and `python -m pytest tests/ -q` to ensure tests pass (use -q not -v to keep output compact; if tests fail, rerun the failing file with -v to debug).

# COMMIT

Make a git commit. The commit message must:

1. Start with `discal:` prefix
2. Include issue number and title
3. Files changed
4. Key decisions made

Keep it concise.

# THE ISSUE

If the task is not complete, leave a comment on the issue with what was done.

Do not close the issue - this will be done later.

Once complete, output <promise>COMPLETE</promise>.

# FORBIDDEN FILES

**Never modify these unless the issue explicitly says to:**

- `.claude/` — agent context files (AGENTS.md, CLAUDE.md, context/*)
- `.sandcastle/` — config files (main.mts, *.md prompts, Dockerfile)
- `.pi/` — project skills

These are the project's agent infrastructure. Touching them outside of a scoped ticket corrupts future agent sessions.

# OFFGASSING

If you notice a bug, have a suggested context update, or want to flag anything out of scope for the current issue, create a file in `.notes/` (gitignored). Do NOT commit it.

**File naming:** `sc-extra-{YYYY-MM-DD}-{issue-slug}-{severity}.md`

**Severity levels:**

| Level | When to use |
|---|---|
| `critical` | Security issue, credential leak, data loss risk — must fix immediately |
| `high` | Bug that affects functionality, incorrect context that will mislead agents |
| `medium` | Suggested improvement, refactoring opportunity, context gap |
| `low` | Minor observation, nice-to-have, documentation nit |

**Format:**

```markdown
# SC Extra: {one-line summary}

**Issue:** #{{TASK_ID}} — {{ISSUE_TITLE}}
**Date:** {YYYY-MM-DD}
**Severity:** {level}

## Observation

[What you noticed]

## Recommendation

[What should be done about it]
```

If `.notes/` doesn't exist, create it. One file per observation — don't lump unrelated things together.

Do NOT commit `.notes/` or any files within it.

# FINAL RULES

ONLY WORK ON A SINGLE TASK.
Do NOT modify `.claude/`, `.sandcastle/config`, or `.pi/` unless the issue explicitly says to.
