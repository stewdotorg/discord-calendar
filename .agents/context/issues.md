# Issue State — Canonical Reference

**Do NOT list individual issues in this file.** Issue state changes constantly and this file would go stale.

## Canonical source

GitHub Issues on `stewdotorg/discord-calendar` is authoritative for all issue state:

```bash
gh issue list --repo stewdotorg/discord-calendar --state open
```

## Labels

| Label | Meaning |
|---|---|
| `ready-for-agent` | Spec is settled; an agent can implement it |
| `needs-triage` | Needs human review first. Never mark `ready-for-agent` without user confirmation. |
