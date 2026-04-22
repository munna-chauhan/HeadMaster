# HeadMaster — Architecture Reference

Path lookup, state location, file conventions. Load only sections you need.

---

## Layer Architecture

| Layer | Path | Invoke | Purpose |
|-------|------|--------|---------|
| Skills | `.claude/skills/` | `/skill-name` | SDLC process (primary entry) |
| Commands | `.claude/commands/` | `/command-name` | Atomic git/utility ops |
| Agents | `.claude/agents/` | Loaded by skills | Behavioral constraints |

**Pipeline skills (5):** `/plan`, `/design`, `/breakdown`, `/execute`, `/navigate`  
**Execution phase skills (5):** `/implement`, `/security-scan`, `/review-code`, `/qa-integration`, `/review-system`  
**Utility skills (3):** `/jira-ops`, `/draw`, `/compress`  
**Commands (5):** `/commit`, `/create-branch`, `/create-pr`, `/handoff`, `/ask-user`  
**Scripts (10):** `compress.py`, `gate_transition.py`, `failure_ledger.py`, `convergence_check.py`, `secret_scanner.py`, `jira_ops.py`, `input_extractor.py`, `diff_scanner.py`, `test_infra_detector.py`, `git_guard.py`  
**Hooks (8):** `activate.py`, `feature_context.py`, `session_reset.py`, `token_budget.py`, `read_compressor.py`, `post_tool.py`, `statusline.py`, `auto_braindump.py`  
**Stop Checks (4):** `plan_stop.py`, `design_stop.py`, `breakdown_stop.py`, `execute_stop.py` (in `.claude/hooks/stop_checks/`)

---

## Memory Systems

**Feature-scoped:** `memory/features/{slug}/`  
Per-feature state, discarded after ship.  
Contains: `loop_state.json`, session handoffs, agent context, phase artifacts.

**Agent-scoped:** `.claude/agent-memory/{agent}/`  
Cross-feature learnings, persists until project deleted.  
Managed by Claude Code Agent tool (automatic).

## Pipeline State

Source of truth: `memory/features/{slug}/loop_state.json` → `pipeline` key.  
Skills call `python3 scripts/gate_transition.py {slug} {phase} {stage}` on every gate pass.

---

## File Conventions

**Feature work:**
```
docs/features/{slug}/
  planning/   → PRD.md, FEATURE_DRAFT.md, DISCOVERY_NOTES.md, PRD_REVIEW.md
  design/     → SYSTEM_DESIGN_NOTES.md, TDD*.md, TDD_REVIEW.md
  breakdown/  → JIRA_BREAKDOWN.md
  execution/  → reviews/security-scan-*.md, code-review-*.md, qa-report-*.md
  retrospective/ → system-review.md
```

**Session state:**
```
memory/features/{slug}/
  loop_state.json                    → pipeline phase, iteration, complexity tier
  session-{ts}.md                    → manual handoffs (/handoff)
  session-{ts}-auto-braindump.md     → auto checkpoints (🟠 threshold)
  agents/{developer,qa,review}.md    → per-story context
```