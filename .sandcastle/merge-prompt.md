# TASK

Merge the following branches into the current branch:

{{BRANCHES}}

For each branch:

1. Run `git merge <branch> --no-edit`
2. If there are merge conflicts, resolve them intelligently by reading both sides and choosing the correct resolution
3. After resolving conflicts, run `ruff check src/ tests/` and `python -m pytest tests/ -q` to verify everything works (use -q not -v to keep output compact; if tests fail, rerun with -v to debug)
4. If tests fail, fix the issues before proceeding to the next branch

**Merge conflict rule:** If a conflict involves `.claude/`, `.sandcastle/`, or `.pi/` files, prefer the current branch (HEAD) version. These are agent infrastructure files — only modify them if the branch was explicitly scoped to do so.

After all branches are merged and tests pass, push each individual branch to origin:

For each branch in the list:
```bash
git push origin <branch>
```

Do NOT push main — the maintainer handles that separately.

Then make a single commit summarizing the merge.

# CLOSE ISSUES

For each issue in the list below, close it:

`gh issue close <issue-id> --comment "Completed by Sandcastle"`

Here are all the issues:

{{ISSUES}}

Once you've merged everything you can, output <promise>COMPLETE</promise>.
