---
name: curate-memory
description: "Deduplicate and age-out entries in an agent's MEMORY.md. /curate-memory <agent> or /curate-memory --all"
argument-hint: <agent> | --all
---

<SUBAGENT-STOP>
If dispatched as a subagent, skip this skill.
</SUBAGENT-STOP>

# Curate Memory

Deduplicate and age-out entries in agent MEMORY.md files.

---

## Usage

```
/curate-memory <agent>
/curate-memory --all
```

---

## Workflow

### 1. Resolve targets

- `<agent>` → single file: `memory/agents/{agent}/MEMORY.md`
- `--all` → all files matching `memory/agents/*/MEMORY.md`

### 2. Run curation

```bash
sh scripts/curate_agent_memory.py {agent}          # single agent
sh scripts/curate_agent_memory.py --all            # all agents
```

Add `--dry-run` to preview without writing.

### 3. Report

Print per-agent summary from script stdout. No further action required.

---

## Notes

- Threshold 0.40 (looser than append dedup at 0.60) — catches paraphrases that slipped through
- Age-out: entries older than 90 days removed
- `.bak` written before any change
- Exit 0 = changes written | Exit 1 = no changes needed | Exit 2 = error