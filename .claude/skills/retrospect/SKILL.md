---
name: retrospect
description: "Self-learning retrospective. /retrospect <slug> — analyzes completed feature run, auto-applies memory entries and learnings, routes config proposals to config-proposals.md."
argument-hint: <feature-slug>
---

<SUBAGENT-STOP>
If dispatched as a subagent, skip this skill.
</SUBAGENT-STOP>

# Retrospect

Analyzes a completed feature run and auto-applies learnings. Config changes are never auto-applied.

---

## Usage

```
/retrospect <slug>
```

Run after a feature's PR is created.

---

## Workflow

### 1. Load run data

```bash
sh scripts/skill_setup.py {slug}
```

Read from `memory/features/{project}/{slug}/`:
- `loop_state.json` — tier, route, escalations, gate timestamps
- `run-log.md` — phase transitions, rework events, loop counts, blockers

### 2. Spawn retrospective-analyst

Spawn `.claude/agents/retrospective-analyst.md` with **only** these two files.

Write output to `memory/features/{project}/{slug}/RETROSPECTIVE.md`.

### 3. Apply by proposal type — no human gate

Read proposals from `RETROSPECTIVE.md` and apply immediately based on type:

**`agent_memory` proposals → auto-apply:**
```bash
sh scripts/update_agent_memory.py {agent} append "{entry}"
```
Dedup check runs inside the script — skipped silently if too similar to an existing entry.

**`pipeline_learning` proposals → auto-apply:**
Append to `memory/pipeline-learnings.md` under the matching section (Tier Calibration / Common Rework Patterns / Agent Behavior). Create file from template if absent.

**`config` proposals → route to config-proposals.md, never auto-apply:**
```bash
# Append to memory/config-proposals.md
[{date}] {slug}: {config_key} → {proposed_value} | evidence: {evidence}
```
Surface to user: "N config proposals recorded in memory/config-proposals.md for your review."

**`workflow` proposals → route to config-proposals.md, never auto-apply:**
Same as config — record, surface, do not edit skill or workflow files.

### 4. Report

Print a concise summary:
```
Retrospective: {slug}
  Memory patches applied:   N  (M skipped — duplicate)
  Pipeline learnings added: N
  Config proposals recorded: N  → memory/config-proposals.md
```

---

## pipeline-learnings.md Template

```markdown
# Pipeline Learnings

Append-only. Updated automatically by /retrospect.
Entries >90 days old move to pipeline-learnings-archive.md.

## Tier Calibration

## Common Rework Patterns

## Agent Behavior
```

---

## Notes

- `retrospective-analyst` uses haiku — fast, pattern extraction only
- Memory entries and learnings auto-apply because they are derived from factual run data
- Config/workflow changes always require deliberate human decision — never auto-applied
- When `memory/agents/{agent}/MEMORY.md` approaches 200 lines, run `/curate-memory {agent}` — deduplicates and ages out entries older than 90 days. The cap is enforced by `update_agent_memory.py`; entries beyond it are dropped until curation runs.
- Phase A/B retry patterns are written per-story by `scripts/extract_phase_learnings.py` — do not re-extract from run-log what the script already captured.
