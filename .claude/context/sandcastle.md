# Sandcastle AFK Workflow

We use [Matt Pocock's Sandcastle](https://github.com/ai-hero/sandcastle) — an AFK software factory that reads `ready-for-agent` GitHub issues and autonomously implements, reviews, and merges them.

- **Config:** `.sandcastle/` — prompts, Dockerfile, main.mts
- **Run:** `npm run sandcastle` from project root
- **Readings:** `~/dev/ai-swe/reading/matt-pocock/afk-workflow/afk-software-factory/` (walkthrough.md, summary.md)
- **Logs:** `.sandcastle/logs/`
- **Limitations:** Sandcastle runs in Docker with no Google API credentials — cannot record VCR cassettes or deploy. Good for: writing code, running non-secret tests, pushing branches. The merger handles merging + ruff + pytest.

## Skills for preparing AFK issues

Project-local skills in `.pi/skills/`:
- `prepare-afk-bugfix/SKILL.md` — interview user about a bug, create tracer-bullet issues, present plan
- `prepare-afk-feature/SKILL.md` — interview user about a feature, design vertical slices, create issues

Both follow interview guidelines: numbered questions, multiple choice with recommendations.

## Running only the reviewer phase

If a sandcastle run crashes after implement but before review, you can run just the reviewer on the existing branch:

```bash
npx tsx .sandcastle/review-only.mts sandcastle/issue-<N>-<slug>
```

This uses `createSandbox()` + `sandbox.run()` with `review-prompt.md`. The script reuses the existing worktree if still alive, or creates a new sandbox on the existing branch.

The review prompt uses `{{TARGET_BRANCH}}` (main) as the diff base and `{{BRANCH}}` (from promptArgs) as the feature branch. This was fixed from `{{SOURCE_BRANCH}}` which was always equal to `{{BRANCH}}`.

## Infinite-loop guard (main.mts)

If the merge phase is skipped (e.g. crash before merge, or reviewer-only script added commits), branches with existing unmerged commits would loop forever: the planner re-schedules them, the implementer produces zero new commits, merge is skipped again. `main.mts` now checks `git log main..<branch> --oneline` after the implementer phase and includes branches with pre-existing commits in the merge list.
