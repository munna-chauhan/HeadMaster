---
name: plan
description: "Smart planning. Two modes: /plan <slug> (auto-detect + resume), /plan <slug> <message> (act on intent). Raw input → finalized PRD."
argument-hint: <feature-slug> [message]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Plan

Mission: Raw input → finalized PRD. Source of truth = `PRD.md`.

---

## Planning Workflow

**Execution = tier.status ⊗ config.gates**

| Tier | PRD Stage     | PRD_REVIEW Stage   |
|------|---------------|-------------------|
| xs   | skip          | skip               |
| s    | required      | skip               |
| m    | required      | optional           |
| l    | required      | required           |

**Gates:**
- `gates.plan.interactive` — Discovery Q&A (true=ask, false=resolve)
- `gates.plan.review.mode` — Review execution (human_in_loop | auto | skip)

**Output to /design:**
- PRD.md (if created, Status=APPROVED) OR FEATURE_DRAFT.md (if PRD skipped)
- Never: DISCOVERY_NOTES.md, PRD_REVIEW.md, input/*.md (internal artifacts)

---

## Modes

**`/plan <slug>`** — auto-detect state, resume from where it left off.

**`/plan <slug> <message>`** — message routed by `planning_stages`:

| Stage state | Message handling |
|-------------|-----------------|
| context in_progress | append to `USER_CONTEXT.md`, resume Context |
| discover in_progress | append as answer/clarification to FEATURE_DRAFT.md or DISCOVERY_NOTES.md, resume Discover |
| draft complete / review pending | apply as PRD feedback inline, enter Review |
| review approved | Reopen flow — see Reopen section |

`review` as a message keyword → no special routing. Treated as feedback, same path as above.

---

## Brainstorm Gate

Fresh features only. Restate problem → 2-3 approaches (table: Approach | Strengths | Risks) → select one, log to `memory/features/{project}/{slug}/brainstorm.md`. Skip on resume or PRD reopen.

---

## Stages

| Stage    | Workflow Key   | Pattern          | Agent                  | Artifact           |
|----------|----------------|------------------|------------------------|--------------------|
| Context  | feature_draft  | Skill + subagent | `codebase-analyst`     | FEATURE_DRAFT.md   |
| Discover | discovery      | Direct           | `requirements-analyst` | DISCOVERY_NOTES.md |
| Draft    | prd            | Direct           | `prd-author`           | PRD.md             |
| Review   | prd_review     | Direct           | `prd-reviewer`         | PRD_REVIEW.md      |

Flow: `Brainstorm (fresh only) → Context → Discover → Draft → Review`
Loop-backs: `DISCOVERY_GAP` → Discover. `PRD_ISSUE` → Draft. Mixed → Discover first.

**Lazy loading:** Load ONLY active stage file (`.claude/skills/plan/stages/{stage}.md`). Never pre-load all stages.

---

## State Detection

**IMPORTANT:** Use `{project}` from Setup step 1. Never hardcode project name.

Read `planning_stages` from `loop_state.json`. Route to first incomplete stage:

```
review = approved                  → FINALIZED. If message → REOPEN (see Reopen section).
review = approved + message        → REOPEN
review = pending, draft = complete → REVIEW SESSION. Must run in new session (see Review stage).
draft  = complete + message        → apply message as PRD feedback, enter Review.
draft  = pending | in_progress     → resume Draft
discover = complete                → start Draft
discover = pending | in_progress   → resume Discover
context  = complete                → start Discover
else (planning_stages absent)      → start Context
```

`pipeline.phase = "init"` is valid — start at Context stage.

---

## Setup (every invocation)

```bash
sh scripts/skill_setup.py {slug}
```

Use `project`, `project_key`, `tier`, `max_loops`, `gates.plan` from output. If `error` is set → HALT. Detect state → load corresponding stage file.

---

## Route Check (after PRD APPROVED)

After `artifacts["planning/PRD.md"].status = approved` in loop_state.json is confirmed, evaluate route reclassification per `.claude/workflows/reclassification.yml` `route_checkpoints.after_plan`:

1. Read current route from `loop_state.json`
2. Check evidence signals against `route_checkpoints.after_plan.checks`
3. If a reclassification is warranted:
   - Follow `route_behavior.supervised` (or `autonomous`)
   - On CHANGE: call `gate_transition.py {project} {slug} reclassify --route {new} --from {old} --checkpoint after_plan --evidence "{signals}"`
   - Apply `route_rework` steps for the detected transition
4. If no reclassification: log `route_check: no change` to run-log.md and continue

Spike route is never reclassified.

---

## Reopen Finalized PRD

Edit PRD directly (single source of truth). Downstream invalidation: if Design is COMPLETE and sections 3-6 edited → mark `design_status: "STALE"` in loop_state.json. If Breakdown is COMPLETE and any section edited → mark `breakdown_status: "STALE"`. Warn only, do not block. Non-functional edits (Background/Glossary/Appendix): skip Review. Functional edits: remove APPROVED gate → Review → re-add gate with incremented iteration count.

---

## PRD Header Standard

Required table fields: Technical Owner, Date, Approver, **PRD Status** (last row, bold = gate string). Read `Technical Owner`/`Approver` from loop_state.json. Never add "PRD Status: APPROVED" as a separate line — header table only. No Change Log sections.

---

## Prerequisites

- **Recommended:** Run `/init-feature` first to classify tier and set up feature directory
