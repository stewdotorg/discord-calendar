# Issue State — Canonical Reference

**Do NOT list individual issues in this file.** Issue state changes constantly and this file will go stale.

## Canonical source

GitHub Issues on `stewdotorg/discord-calendar` is authoritative for all issue state. Run this to see current open issues:

```bash
gh issue list --repo stewdotorg/discord-calendar --label ready-for-agent
gh issue list --repo stewdotorg/discord-calendar --state open
```

## Labels

| Label | Meaning |
|---|---|
| `ready-for-agent` | Sandcastle can pick it up |
| `needs-triage` | Human review needed first — never mark `ready-for-agent` without user confirmation |

## Workflow

1. Issues start as `needs-triage` during human discussion/design
2. After user approval, label changes to `ready-for-agent`
3. Sandcastle picks up `ready-for-agent` issues, implements, and merges
4. GitHub is always authoritative — never trust a stale context file over `gh issue list`
