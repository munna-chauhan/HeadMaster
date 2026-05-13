## What

<!-- One sentence. Which PLAN.md PR does this address? -->

## Changes

<!-- File-by-file bullet list of what changed and why. -->

## Checklist

- [ ] `python scripts/audit_inventory.py` exits 0
- [ ] `python scripts/config_utils.py validate config.yml` exits 0 (if config.yml exists locally)
- [ ] `pytest scripts/tests/ -q` exits 0
- [ ] Changes to `.claude/agents/`, `.claude/skills/`, `.claude/workflows/`, `.claude/hooks/`, `.claude/settings.json`, `scripts/gate_transition.py`, `scripts/state_manager.py`, `scripts/config_utils.py`, or `.mcp.json` have human approval (unconditional gate — see CLAUDE.md Contribution Rules)
