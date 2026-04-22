---
name: breakdown
description: "TDD → Jira stories + epic (Breakdown), then post-execution PR checklist (Merge Gate). Human approval unconditional at both stages."
argument-hint: <feature-slug> [merge-gate]
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python .claude/hooks/stop_checks/breakdown_stop.py $ARGUMENTS"
          timeout: 10
  PostToolUse:
    - matcher: "Bash"
      hooks:
      - type: prompt
        model: haiku
        timeout: 15
        prompt: |
          A Bash command just ran. Parse $ARGUMENTS as JSON.
          Check tool_input.command field.

          If command contains 'jira' and ('create' or 'update' or 'add-label'):
            Verify output contains a Jira issue key (e.g. PROJ-123).
            If no key in output → return {"ok": false, "reason": "Jira op may have failed — no issue key in output"}

          All other commands: return {"ok": true}

          Return {"ok": true} if valid.
          Return {"ok": false, "reason": "<what failed>"} if not.
---

# Breakdown

Load `.claude/agents/release-agent.md` + `.claude/commands/ask-user.md` before executing. Verify `config.yml` exists. If absent → HALT. Read: `project_key`, `jira_push`, `interactive`.

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
| JIRA_BREAKDOWN.md exists + Push Status | Breakdown done, report status |
| JIRA_BREAKDOWN.md exists + no Push Status | Resume from human gate (Step 7) |
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
- All stories COMPLETE
- System review passed

---

## Stage Files

Load only the active stage:

**Breakdown:** `.claude/skills/breakdown/stages/decompose.md` (Steps 1-8)  
**Merge Gate:** `.claude/skills/breakdown/stages/merge-gate.md`

Each stage file is self-contained. Do not load both simultaneously.

---

## Memory

After Breakdown, update `memory/features/{slug}/agents/release-agent.md`:
- Sizing decisions, merge/split rationale, epic structure, parallel groups
- Dependency patterns, cross-repo splits, relationship types
