---
name: plan
description: "Smart planning. Two modes: /plan <slug> (auto-detect + resume), /plan <slug> <message> (act on intent). Raw input → finalized PRD."
argument-hint: <feature-slug> [message]
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python .claude/hooks/stop_checks/plan_stop.py $ARGUMENTS"
          timeout: 10
---

# Plan

Mission: Raw input → finalized PRD. Source of truth = `PRD.md`.

---

## Modes

**`/plan <slug>`** — auto-detect state, resume. Looks for `FEATURE_INPUT.md` in HeadMaster root if no feature dir.

**`/plan <slug> <message>`** — parse intent. New feature → start fresh. In progress → treat as context. Finalized → reopen, apply feedback, re-validate.

---

## Stages

| Stage    | Pattern          | Agent                  | Artifact           |
|----------|------------------|------------------------|--------------------|
| Init     | Skill + subagent | `codebase-analyst`     | FEATURE_DRAFT.md   |
| Discover | Direct           | `requirements-analyst` | DISCOVERY_NOTES.md |
| Draft    | Direct           | `prd-author`           | PRD.md             |
| Review   | Subagent         | `prd-reviewer`         | PRD_REVIEW.md      |

Flow: `Init → Discover → Draft → Review`
Loop-backs: `DISCOVERY_GAP` → Discover. `PRD_ISSUE` → Draft. Mixed → Discover first.

Each stage in `.claude/skills/plan/stages/{stage}.md`. Load only the active stage.

---

## State Detection

Check `docs/features/{slug}/planning/`:

```
PRD.md + "PRD Status: APPROVED"          → FINALIZED (or reopen if message)
PRD.md + loop_state blocker              → Review loop-back
PRD.md                                   → start Review
DISCOVERY_NOTES.md ends with YES         → resume Draft
DISCOVERY_NOTES.md without YES           → resume Discover
FEATURE_DRAFT.md exists                  → resume Discover
Nothing                                  → start Init
```

---

## Setup (every invocation)

1. Read `config.yml` → `project_key`, `max_loops`, `interactive`. If absent → HALT.
2. Check `memory/features/{slug}/loop_state.json` → loop count + `complexity_tier` (managed by `convergence_check.py`, never write manually)
3. Verify `.claude/workflows/complexity-tiers.yml` exists. If absent → HALT. Load tier (default: `full` → 14 sections, standard → 10, lite → 6)
4. Detect state → load corresponding stage file

---

## Reopen Finalized PRD

`/plan <slug> <message>` on APPROVED PRD:

1. Parse intent from `<message>`
2. Minor → edit sections directly. New requirement → add to sections. Major → re-run Discover for new questions only.
3. Remove gate string → run Review → re-add on pass.

---

## PRD Header Standard

All PRD documents use this table — no freeform headers. Required fields marked *.

```markdown
# {Feature Name}

| Field            | Value                              |
|------------------|------------------------------------|
| Technical Owner* | {name from input or Jira}          |
| Status*          | Draft \| In Review \| Approved     |
| Date*            | {ISO-date}                         |
| Approver*        | {name or TBD}                      |
| Project          | {project_key from config.yml}      |
| Feature Folder   | docs/features/{slug}               |
| Complexity Tier  | lite \| standard \| full           |
| AI Co-Author     | prd-author (AI-Generated)          |
| Confidence       | {1-10}/10 — {rationale}            |
| Jira Epic        | {EPIC-KEY or N/A}                  |
| Iterations       | {N}                                |
| Next Step        | /design {slug}                     |
```

On completion: Status → `Approved`, Iterations → final count, Next Step → `/design {slug}`.

---

## Prerequisites

- Feature description (text/Jira/Confluence) or `FEATURE_INPUT.md` in HeadMaster project root
- `config.yml` at HeadMaster project root
