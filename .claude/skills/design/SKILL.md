---
name: design
description: "Technical design pipeline. /design <slug> (auto-detect + resume, reads PRD by default), /design <slug> <message> (focus hint or override). PRD → SYSTEM_DESIGN_NOTES + TDD(s). Working files kept."
argument-hint: <feature-slug> [message]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

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

| Stage     | Pattern           | Agent                                                 | Output                                                                       | Session  |
|-----------|-------------------|-------------------------------------------------------|------------------------------------------------------------------------------|----------|
| Architect | Skill + subagents | `solutions-architect` + `codebase-analyst` (parallel) | SYSTEM_DESIGN_NOTES.md                                                       | current  |
| Engineer  | Direct            | `tdd-author`                                          | TDD.md or TDD_MASTER.md + TDD_{REPO}.md(s) + MIGRATION_PLAN.md (conditional) | current  |
| Review    | Direct            | `tdd-reviewer` (inline)                               | TDD_REVIEW.md                                                                | new      |

Flow: `Architect → Engineer → [stop] → Review (new session)`
Loop-backs: `TDD_ISSUE` → Engineer. `DESIGN_GAP` → Architect. Mixed → Architect first.

---

## State Detection

Read `design_stages` from `memory/features/{project}/{slug}/loop_state.json`:

| `design_stages` state                        | Action                          |
|----------------------------------------------|---------------------------------|
| `review = approved`                          | COMPLETE — nothing to do        |
| `review = in_progress` (new session resume)  | Load → execute review.md        |
| `engineer = complete` (new session start)    | Load → execute review.md        |
| `engineer = in_progress`                     | Resume Engineer stage           |
| `architect = complete`                       | Start Engineer stage            |
| `architect = in_progress`                    | Resume Architect stage          |
| not set / all pending                        | Start Architect stage           |
| `pipeline.design_blocker = DESIGN_GAP`       | Resume Architect (gap-only)     |
| `pipeline.design_blocker = TDD_ISSUE`        | Resume Engineer (fix only)      |

xs tier override: if `tier = xs` → skip Architect, go direct to Engineer (IMPLEMENTATION_BRIEF.md). No review.

---

## Setup (every invocation)

```bash
python scripts/skill_setup.py {slug}
```

Use `project`, `project_key`, `tier`, `max_loops`, `gates.design` from output. If `error` is set → HALT.

Read `.claude/workflows/{tier}.yml` for `stages.tdd.sections` and `stages.tdd_review.status`.

If `<message>`: log as focus hint.

**Tier determines design depth:**
- **xs** → Skip Architect stage. Write IMPLEMENTATION_BRIEF.md (5 sections). No TDD review.
- **s/m/l** → Full Architect + Engineer + Review stages. TDD.md sections: s=8, m=10, l=11.

---

## Stage Dispatch

Based on detected state, load and execute the corresponding stage file:

| State     | Action                                                       |
|-----------|--------------------------------------------------------------|
| Architect | Load and execute `.claude/skills/design/stages/architect.md` |
| Engineer  | Load and execute `.claude/skills/design/stages/engineer.md`  |
| Review    | Load and execute `.claude/skills/design/stages/review.md`    |

---

## Route Check (after TDD APPROVED)

After `TDD Status: APPROVED` (or IMPLEMENTATION_BRIEF complete for xs), evaluate route reclassification per `.claude/workflows/reclassification.yml` `route_checkpoints.after_design`:

1. Check evidence signals: multi-repo split required? Phased rollout not in PRD? New integration points in SYSTEM_DESIGN_NOTES?
2. If reclassification warranted: follow `route_behavior` and apply `route_rework` steps
3. `gate_transition.py {project} {slug} reclassify --route {new} --from {old} --checkpoint after_design --evidence "{signals}"`
4. If no change: log `route_check: no change` and continue to `/breakdown`

Spike and hotfix routes are not reclassified at design checkpoint.

---

## Prerequisites

- `docs/features/{project}/{slug}/planning/PRD.md` with `PRD Status: APPROVED`
- `config.yml` at repo root
