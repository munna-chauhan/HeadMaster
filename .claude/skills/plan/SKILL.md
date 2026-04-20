---
name: plan
description: "Smart planning. Two modes: /plan <slug> (auto-detect + resume), /plan <slug> <message> (act on intent). Raw input → finalized PRD. Working files kept for traceability."
argument-hint: <feature-slug> [message]
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python .claude/hooks/stop_checks/plan_stop.py $ARGUMENTS"
          timeout: 10
---

# Plan

Mission: Raw input → finalized PRD. Single source of truth = `PRD.md`. Working files temporary.

---

## Modes

**`/plan <slug>`** — auto-detect state, act.

- No feature dir → look for `FEATURE_INPUT.md` in repo root. Not found → ask user.
- Feature exists → resume from last state.
- PRD finalized → report status. Nothing to do.

**`/plan <slug> <message>`** — parse intent.

- No feature → use `<message>` as description. Start fresh.
- In progress → continue from last state, treat message as context.
- PRD finalized → reopen, apply feedback, re-validate.

---

## Stages

| Stage    | Pattern          | Agent                         | Working File       | Output             |
|----------|------------------|-------------------------------|--------------------|--------------------| 
| Init     | Skill + subagent | `codebase-analyst` (parallel) | FEATURE_DRAFT.md   | —                  |
| Discover | Direct           | `requirements-analyst`        | DISCOVERY_NOTES.md | —                  |
| Draft    | Direct           | `prd-author`                  | —                  | PRD.md             |
| Review   | Subagent         | `prd-reviewer`                | —                  | PRD.md (validated) |

Flow: `Init → Discover → Draft → Review`
Loop-backs: `DISCOVERY_GAP` → Discover. `PRD_ISSUE` → Draft. Mixed → Discover first.

---

## State Detection

Check `docs/features/{slug}/planning/`:

```
PRD.md + gate string                     → FINALIZED (report status, or reopen if message)
PRD.md + no gate string + loop_state blocker → Review loop-back in progress
PRD.md + no gate string                  → start Review
DISCOVERY_NOTES.md ends with YES         → resume Draft
DISCOVERY_NOTES.md without YES           → resume Discover
FEATURE_DRAFT.md exists                  → resume Discover
Nothing                                  → start Init
```

Gate string (end of PRD.md): `PRD Status: APPROVED`

---

## Setup (every invocation)

1. Read `config.yml` → `project_key`, `max_loops` (default 3), `interactive`
2. Check `memory/features/{slug}/loop_state.json` → loop count + `complexity_tier`
3. Read `.claude/workflows/complexity-tiers.yml` → load tier definition for `complexity_tier` (default: `full`)
4. Detect state
5. If `<message>`: parse intent

**Tier determines PRD depth:** lite=6 sections, standard=10 sections, full=14 sections.

---

## Stage Dispatch

Based on detected state, load and execute the corresponding stage file:

| State         | Action                                                    |
|---------------|-----------------------------------------------------------|
| Init          | Load and execute `.claude/skills/plan/stages/init.md`     |
| Discover      | Load and execute `.claude/skills/plan/stages/discover.md` |
| Draft         | Load and execute `.claude/skills/plan/stages/draft.md`    |
| Review        | Load and execute `.claude/skills/plan/stages/review.md`   |

---

## AskUserQuestion Format

See `.claude/commands/ask-user.md` for full format, decision rules, and navigation commands.

---

## Reopen Finalized PRD

`/plan <slug> <message>` on APPROVED PRD:

1. Read PRD.md + parse intent from `<message>`
2. Minor feedback → edit sections directly → run Review
3. New requirement → add to relevant sections → run Review
4. Major change → recreate DISCOVERY_NOTES.md for new questions only
5. Remove `PRD Status: APPROVED`
6. Run Review stage
7. On pass → re-add gate string

---

## Loop State

Path: `memory/features/{slug}/loop_state.json`

Managed by `scripts/convergence_check.py`. Do NOT write loop_state manually during review rejection.

---

## Completion

```
Planning complete: {slug}

PRD.md — {N}/{tier-required} sections (tier: {complexity_tier})
Confidence: {N}/10
Iterations: {N}
Working files retained for traceability.

Next: /design {slug}
```

---

## Prerequisites

- Feature description (text/Jira/Confluence) or `FEATURE_INPUT.md` in repo root
- `config.yml` at repo root
