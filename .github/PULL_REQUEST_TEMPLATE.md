## Summary

- What changed and why (1–3 bullets).

## Scope

- Files / components touched.
- Pipeline phases affected.

## Validation

- [ ] `pytest scripts/tests/ -q` green
- [ ] `python scripts/audit_inventory.py` green
- [ ] `python scripts/config_utils.py validate config.yml.example` green
- [ ] If `.claude/agents/`, `.claude/skills/`, `.claude/workflows/`, `.claude/hooks/`, `.claude/settings.json`, or a guarded script changed → human approval requested in this PR (per `.claude/CLAUDE.md` Contribution Rules)

## Notes

Anything reviewers should know — backwards-incompatibility, follow-ups, deferred work.
