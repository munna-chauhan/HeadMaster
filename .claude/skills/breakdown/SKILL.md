---
name: breakdown
description: "TDD → Jira stories + epic (Breakdown), then post-execution PR checklist (Merge Gate). Human approval unconditional at both stages."
argument-hint: <feature-slug> [merge-gate]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Breakdown

**Agents:** `release-agent`

```bash
python scripts/skill_setup.py {slug}
```

Use `project`, `project_key`, `jira_push`, `autonomous` from output. If `error` is set → HALT.

Two stages: **Breakdown** (TDD → stories) and **Merge Gate** (post-execution PR checklist).

---

## Invocation

```
/breakdown {slug}               → Breakdown stage
/breakdown {slug} merge-gate    → Merge Gate stage
```

---

## Stage Detection & Dispatch

Check argument + artifacts:

| Condition | Action |
|-----------|--------|
| Argument = "merge-gate" | Load `.claude/skills/breakdown/stages/merge-gate.md` |
| Any `JIRA_BREAKDOWN*.md` exists + status = `pushed` + `pipeline.revision_open != true` | Breakdown done — report status, offer merge-gate |
| Any `JIRA_BREAKDOWN*.md` exists + status = `pushed` + `pipeline.revision_open = true` | Revision mode — `python scripts/revision_manager.py check {project} {slug} breakdown` → read Breakdown section of open rev_id in `REVISION_NOTES.md`, run decompose treating COMPLETE stories as reconcilable (not skipped) |
| Any `JIRA_BREAKDOWN*.md` exists + status = `local` or `draft` | Resume from Step 7 (human gate) |
| Nothing | Load `.claude/skills/breakdown/stages/decompose.md` |

---

## Skip Condition

```
Route = hotfix or spike → HALT. No breakdown needed.
```

---

## Prerequisites

**Breakdown:**
- TDD*.md OR IMPLEMENTATION_BRIEF.md exists
- PRD.md exists
- config.yml loaded

**Merge Gate:**
- All stories COMPLETE in `loop_state.json` (all `stories.{KEY}.status = COMPLETE`) and `JIRA_BREAKDOWN*.md`
- System review passed

---

## Stage Files

Load only the active stage:

**Breakdown:** `.claude/skills/breakdown/stages/decompose.md` (Steps 1-8)  
**Merge Gate:** `.claude/skills/breakdown/stages/merge-gate.md`

Each stage file is self-contained. Do not load both simultaneously.

---

## Memory

After Breakdown, update `memory/agents/release-agent/MEMORY.md`:
- Sizing decisions, merge/split rationale, epic structure, parallel groups
- Dependency patterns, cross-repo splits, relationship types
