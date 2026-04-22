---
name: design
description: "Technical design pipeline. /design <slug> (auto-detect + resume, reads PRD by default), /design <slug> <message> (focus hint or override). PRD → SYSTEM_DESIGN_NOTES + TDD(s). Working files kept."
argument-hint: <feature-slug> [message]
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python .claude/hooks/stop_checks/design_stop.py $ARGUMENTS"
          timeout: 10
  SubagentStop:
    - hooks:
        - type: prompt
          model: haiku
          timeout: 15
          prompt: |
            A subagent just finished. Parse $ARGUMENTS as JSON.
            Check the 'last_assistant_message' field.

            For codebase-analyst subagents:
              Valid output contains: a markdown table OR the word 'greenfield'.
              Invalid: empty string, 'I cannot', 'no results', or fewer than 20 words.

            For tdd-reviewer subagents:
              Valid output contains: 'APPROVED', 'CONDITIONAL', or 'REJECTED'.
              Invalid: missing all three verdict words.

            For other subagents: return {"ok": true} — no validation needed.

            Return {"ok": true} if output is valid.
            Return {"ok": false, "reason": "Subagent returned incomplete output: <what was missing>"} if invalid.
  PostToolUseFailure:
    - matcher: "Bash"
      hooks:
        - type: command
          command: |
            python3 -c "
import json, sys
data = json.load(sys.stdin)
cmd = data.get('tool_input', {}).get('command', '')
err = data.get('error', 'unknown error')
if 'jira_ops' in cmd:
    out = {'hookSpecificOutput': {'hookEventName': 'PostToolUseFailure', 'additionalContext': f'External data fetch failed: {err}. Continue with partial data. Mark affected SYSTEM_DESIGN_NOTES sections as [UNVERIFIED].'}}
    print(json.dumps(out))
"
        statusMessage: "Handling script failure..."
---

# Design

Load agent per stage (see Stage table). Verify `config.yml` exists at repo root. If absent → HALT.

Mission: PRD → implementation-ready TDD(s). Single source of truth per stage. Working files kept.

---

## Modes

**`/design <slug>`** — auto-detect state, act.

- No design dir → read PRD.md, start Architect stage.
- Design in progress → resume from last state.
- TDD approved → report status. Nothing to do.

**`/design <slug> <message>`** — parse intent.

- `<message>` = focus hint: narrows attention, does not replace any step.
- In progress → continue from last state with focus hint.
- Approved → reopen, apply feedback, re-validate.

---

## Stages

| Stage     | Pattern           | Agent                                                 | Output                                                                       |
|-----------|-------------------|-------------------------------------------------------|------------------------------------------------------------------------------|
| Architect | Skill + subagents | `solutions-architect` + `codebase-analyst` (parallel) | SYSTEM_DESIGN_NOTES.md                                                       |
| Engineer  | Direct            | `tdd-author`                                          | TDD.md or TDD_MASTER.md + TDD_{REPO}.md(s) + MIGRATION_PLAN.md (conditional) |
| Review    | Subagent          | `tdd-reviewer`                                        | TDD_REVIEW.md                                                                |

Flow: `Architect → Engineer → Review`
Loop-backs: `TDD_ISSUE` → Engineer. `DESIGN_GAP` → Architect. Mixed → Architect first.

---

## State Detection

Check `docs/features/{slug}/design/` + `complexity_tier` from loop_state.json:

```
# Lite tier:
IMPLEMENTATION_BRIEF.md exists + 5 sections    → COMPLETE (no review needed)
IMPLEMENTATION_BRIEF.md exists + incomplete     → resume Engineer (lite)
Nothing + tier=lite                             → start Engineer (lite) — skip Architect

# Standard/Full tier:
TDD_REVIEW.md + APPROVED verdict + loop_state design.status=PASS  → COMPLETE
TDD file(s) exist + loop_state DESIGN_GAP                        → resume Architect
TDD file(s) exist + loop_state TDD_ISSUE                         → resume Engineer
TDD file(s) exist + no APPROVED verdict                          → resume Review
SYSTEM_DESIGN_NOTES.md + Architecture Locked: YES                → resume Engineer
SYSTEM_DESIGN_NOTES.md + no lock                                 → resume Architect
Nothing                                                           → start Architect
```

---

## Setup (every invocation)

1. Read `config.yml` → `project_key`, `max_loops` (default 3), `interactive`. If absent → HALT.
2. Check `memory/features/{slug}/loop_state.json` → loop count + last blocker type + `complexity_tier`
3. Verify `.claude/workflows/complexity-tiers.yml` exists. If absent → HALT. Read tier definition for `complexity_tier` (default: `full`)
4. Detect state
5. If `<message>`: log as focus hint

**Tier determines design depth:**
- **lite** → Skip Architect stage. Write IMPLEMENTATION_BRIEF.md (5 sections). No TDD review subagent.
- **standard** → Full Architect stage. Write TDD.md (8 sections). TDD review.
- **full** → Full Architect stage. Write TDD.md (11 sections). TDD review.

---

## Stage Dispatch

Based on detected state, load and execute the corresponding stage file:

| State     | Action                                                       |
|-----------|--------------------------------------------------------------|
| Architect | Load and execute `.claude/skills/design/stages/architect.md` |
| Engineer  | Load and execute `.claude/skills/design/stages/engineer.md`  |
| Review    | Load and execute `.claude/skills/design/stages/review.md`    |

---

## AskUserQuestion Format

Load `.claude/commands/ask-user.md` before any stage that asks questions. Mandatory when `interactive: true`.
After every AskUserQuestion: STOP. Wait for user response. Do not continue.

---

## Loop State

Path: `memory/features/{slug}/loop_state.json`

Managed by `scripts/convergence_check.py`. Do NOT write loop_state manually during review rejection.

---

## Completion

**Lite tier:**
```
Design complete: {slug} (lite tier)
IMPLEMENTATION_BRIEF.md — 5/5 sections
Next: /breakdown {slug}
```

**Standard/Full tier:**
```
Design complete: {slug}
Architect: SYSTEM_DESIGN_NOTES.md — Architecture Locked: YES ({N} ADRs)
Engineer:  {TDD.md | TDD_MASTER.md + {N} repo TDDs} — {N} slices
Review:    TDD_REVIEW.md — {APPROVED | CONDITIONAL}
Iterations: {N}
Next: /breakdown {slug}
```

---

## Prerequisites

- `docs/features/{slug}/planning/PRD.md` with `PRD Status: APPROVED`
- `config.yml` at repo root
