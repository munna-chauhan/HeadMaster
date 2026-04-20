---
name: navigate
description: "Smart entry point. No args = dashboard of all in-progress features. With slug/description = classify, detect progress, resume from last gate. Never restart from scratch."
argument-hint: [ feature-slug or change-description ]
---

# Navigate

Respond concisely throughout. Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths exact.

Mission: No args → feature dashboard. With input → classify + detect + resume plan.

---

## Mode Detection

```
No arguments  → Dashboard mode: scan all docs/features/, show status of every feature
Slug provided → State + Resume mode: show compact state then output execution plan
Description   → New mode: classify route, generate plan, confirm with user
```

---

## DASHBOARD MODE (no args)

Scan `docs/features/*/` — for each feature found:

1. Detect current phase (artifact detection logic below)
2. Read `memory/features/{slug}/loop_state.json` if exists — extract loop counts + last blocker
3. Output one row per feature

```markdown
# Feature Dashboard

| Slug | Phase | Status | Loops | Last Blocker | Next Action |
|------|-------|--------|-------|--------------|-------------|
| my-feature | Planning | IN PROGRESS | planning: 2/3 | DISCOVERY_GAP | /plan my-feature |
| auth-refactor | Execute | IN PROGRESS | — | — | /execute auth-refactor |
| data-sync | Design | BLOCKED | design: 3/3 | DESIGN_GAP | Human review needed |
| old-feature | Merge Gate | COMPLETE | — | — | /breakdown old-feature merge-gate |
```

No features found → "No features in progress. Run `/navigate <description>` to start one."

---

## RESUME / NEW MODE

### Step 0: Compact State Output (slug provided)

Before building the full execution plan, output a quick state block:

```
Feature: {slug}
Phase:   {current phase/stage}
Loops:   planning {N}/{max} | design {N}/{max}
Blocker: {last_blocker_type or —}

Next: {exact command}
```

Read `memory/features/{slug}/loop_state.json` for loop counts. Detect phase from artifacts (Step 1 below). Output this
block first, then continue to full execution plan.

---

### Step 1: Artifact Detection

Scan `docs/features/{slug}/`:

```
planning/PRD.md + "PRD Status: APPROVED"    → Planning complete
planning/PRD.md exists (no gate string)      → /plan {slug} (resume)
planning/DISCOVERY_NOTES.md exists           → /plan {slug} (resume)
planning/FEATURE_DRAFT.md exists             → /plan {slug} (resume)
Nothing in planning/                         → /plan {slug} (start)
design/SYSTEM_DESIGN_NOTES.md exists         → Architect done → /design {slug} (resume)
design/TDD*.md exists                        → Engineer done → /design {slug} (resume)
design/TDD_REVIEW.md + APPROVED              → Design complete
breakdown/JIRA_BREAKDOWN.md exists           → Breakdown done → /execute {slug}
All stories COMPLETE in JIRA_BREAKDOWN.md    → /breakdown {slug} merge-gate
```

Also read `memory/features/{slug}/loop_state.json` if exists:

```json
{
  "planning": {
    "iteration": 2,
    "status": "PASS"
  },
  "design": {
    "iteration": 1,
    "last_blocker_type": "DESIGN_GAP"
  }
}
```

Surface loop counts + last blocker in plan — tells user exactly where friction is.

Resume from first missing gate. Never restart.

---

### Step 2: Change Classification (new features only)

| Question                      | Signal              | Route       |
|-------------------------------|---------------------|-------------|
| Production bug or config fix? | Urgency + known fix | **hotfix**  |
| Single story, known approach? | No design needed    | **story**   |
| Needs requirements + design?  | Discovery required  | **feature** |
| Multiple features or repos?   | Enterprise scale    | **epic**    |

Ambiguous → start `story`, escalate to `feature` if complexity emerges.

---

### Step 3: Plan Output

```markdown
# Execution Plan: {Feature/Story Name}

**Route:** {hotfix | story | feature | epic}
**Resuming From:** {Phase — reason}
**Phases Remaining:** {N}
**Loop State:** planning {N}/{max} | design {N}/{max} | last blocker: {type or —}

## Phase Sequence

| # | Phase | Skill | Status |
|---|-------|-------|--------|
| 1 | Planning  | /plan {slug}                    | SKIP / NEXT / PENDING |
| 2 | Design    | /design {slug}                  | SKIP / NEXT / PENDING |
| 3 | Breakdown | /breakdown {slug}               | SKIP / NEXT / PENDING |
| 4 | Execute   | /execute {slug}                 | SKIP / NEXT / PENDING |
| 5 | Merge Gate| /breakdown {slug} merge-gate    | SKIP / NEXT / PENDING |

**Status:** SKIP = done | NEXT = first action | PENDING = future | BLOCKED = missing prereqs

## Missing Prerequisites

- {anything needed before starting}

## Recommended First Action

`/{skill} {slug}` — always specific, never vague.
```

---

### Step 4: User Confirmation

Present plan, wait. User may: approve, skip phases (with justification), override route, add constraints.

---

## Classification Examples

| Input                                     | Route   |
|-------------------------------------------|---------|
| "500 errors in prod"                      | hotfix  |
| "add search filter to existing UI"        | story   |
| "ES5 to ES9 migration strategy"           | feature |
| "modernize entire payment infrastructure" | epic    |

---

## Prerequisites & Output

**In:** No args (dashboard) or change description/slug
**Out:** Dashboard table or execution plan displayed — not saved unless user requests

**Success:** Route classified, artifacts detected, loop state surfaced, sequence clear, first action specific, user
confirmed
