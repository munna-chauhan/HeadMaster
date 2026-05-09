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

**`/plan <slug> <message>`** — message is routed based on current state:

| State | Message Handling |
|-------|------------------|
| Nothing exists (fresh) | Message becomes **seed input** — write to `input/USER_CONTEXT.md`, use alongside FEATURE_INPUT.md in Context stage |
| FEATURE_DRAFT exists | Message becomes **discovery context** — append to FEATURE_DRAFT.md Section 6 (Gaps) or Section 7 (Questions) as user-provided clarification, then resume Discover |
| DISCOVERY_NOTES in progress | Message becomes **answer/clarification** — append as inline answer to next unresolved question in DISCOVERY_NOTES.md, resume Discover |
| PRD.md exists (not approved) | Message becomes **draft feedback** — parse intent, edit affected PRD sections, resume Review |
| PRD.md APPROVED | **Reopen flow** — see Reopen Finalized PRD section below |

**Message routing rules:** parse intent (requirement/clarification/feedback/correction/scope) → persist to artifact → resume. FEATURE_INPUT.md is primary if init-feature was run.

---

## Brainstorm Gate

Fresh features only. Restate problem → 2-3 approaches (table: Approach | Strengths | Risks) → select one, log to `memory/features/{project}/{slug}/brainstorm.md`. Skip on resume or PRD reopen.

---

## Stages

| Stage    | Workflow Key   | Pattern          | Agent                  | Artifact           |
|----------|----------------|------------------|------------------------|--------------------|
| Context  | feature_draft  | Skill + subagent | `codebase-analyst`     | FEATURE_DRAFT.md   |
| Discover | discovery      | Direct/subagent  | `requirements-analyst` | DISCOVERY_NOTES.md |
| Draft    | prd            | Direct           | `prd-author`           | PRD.md             |
| Review   | prd_review     | Subagent         | `prd-reviewer`         | PRD_REVIEW.md      |

Flow: `Brainstorm (fresh only) → Context → Discover → Draft → Review`
Loop-backs: `DISCOVERY_GAP` → Discover. `PRD_ISSUE` → Draft. Mixed → Discover first.

**Lazy loading:** Load ONLY active stage file (`.claude/skills/plan/stages/{stage}.md`). Never pre-load all stages.

---

## State Detection

**IMPORTANT:** Use `{project}` variable from Setup step 1, never hardcode project name.

Check `docs/features/{project}/{slug}/planning/`:

```
PRD.md + "PRD Status: APPROVED" + message → REOPEN (apply message, see Reopen section)
PRD.md + "PRD Status: APPROVED"           → FINALIZED (nothing to do)
PRD.md + loop_state blocker               → Review loop-back
PRD.md + message                          → apply message as draft feedback, resume Review
PRD.md                                    → start Review
DISCOVERY_NOTES.md ends with YES + msg    → resume Draft (m/l — message as additional context)
DISCOVERY_NOTES.md ends with YES          → resume Draft (m/l)
DISCOVERY_NOTES.md without YES + message  → append message as answer/clarification, resume Discover
DISCOVERY_NOTES.md without YES            → resume Discover
FEATURE_DRAFT.md + "All Gaps Resolved: YES" + msg → apply message as draft feedback, resume Draft (s tier)
FEATURE_DRAFT.md + "All Gaps Resolved: YES"       → resume Draft (s tier — gaps resolved inline)
FEATURE_DRAFT.md + message                → append message to gaps/questions, resume Discover
FEATURE_DRAFT.md                          → resume Discover
Nothing + message                         → write USER_CONTEXT.md, start Context
Nothing                                   → start Context
```

**Note:** `pipeline.phase = "init"` is valid (set by `/init-feature`) — start at Context stage, not an error.

---

## Setup (every invocation)

```bash
python scripts/skill_setup.py {slug}
```

Use `project`, `project_key`, `tier`, `max_loops`, `gates.plan` from output. If `error` is set → HALT. Detect state → load corresponding stage file.

---

## Route Check (after PRD APPROVED)

After the gate `PRD Status: APPROVED` is confirmed, evaluate route reclassification per `.claude/workflows/reclassification.yml` `route_checkpoints.after_plan`:

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
