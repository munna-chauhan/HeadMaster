---
name: review-system
description: "Inline phase E of /execute. Pre-PR process audit — TDD design vs actual execution. Classifies divergences, root-cause analyzes, generates actionable findings + pipeline improvements. One-shot after all stories complete."
argument-hint: <feature-slug>
---

# Review System

Respond concisely throughout. Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths exact.

Load `.claude/agents/release-agent.md` before executing. Compare what was designed vs what was built. Find process bugs,
not code bugs.

---

## Input (from orchestrator)

```
slug,
execution_log,    ← JIRA_BREAKDOWN.md Execution Log section
tdd_ref,          ← path to TDD*.md files
prd_repos,        ← PRD S12 repo specs (build tools, stacks)
review_artifacts  ← paths to all execution/reviews/*.md files
```

---

## Step 1: Read Context (single pass)

Read once, extract, discard raw content:

1. `docs/features/{slug}/breakdown/JIRA_BREAKDOWN.md` — Execution Log only
2. `docs/features/{slug}/design/TDD*.md` — design blueprint
3. `docs/features/{slug}/planning/PRD.md` S12 — repo specs for stack compliance
4. All `docs/features/{slug}/execution/reviews/*.md` — code-review, security-scan, qa-report artifacts

**Do NOT re-read files.** Reference by section in later steps.

---

## Step 2: Adherence Analysis

Per story in Execution Log:

- Implementation match TDD interfaces + component design?
- Repeated failures at same phase? → signals TDD gap or agent drift
- Security-scan found issues TDD design should have prevented?
- QA rejected for bugs TDD test strategy should have caught?
- TDD deviations flagged in code-review artifacts?
- Stack compliance: correct build tool + test runner per PRD S12?

**Divergence examples:**

- TDD: `PreparedStatement` → Actual: raw SQL concat → Problematic (security violation)
- TDD: `OrderRepository` → Actual: `OrderDAO` → Problematic (arch drift)
- TDD: yarn per PRD S12 → Actual: yarn → Justified (correct)
- Story needed 3 implement attempts → TDD section underspecified

---

## Step 3: Divergence Classification

**Justified (adaptive):**

- TDD technically incomplete, agent adapted correctly
- Agent used PRD S12 tools over TDD assumptions
- Agent followed codebase convention not in TDD

**Problematic (violation):**

- Invented components not in TDD
- Skipped required tests
- Security constraint violated (hardcoded creds, raw SQL)
- Ignored PRD S12 tool specs

---

## Step 4: Root Cause Analysis

Per divergence:

- **TDD incompleteness** — section didn't specify clearly enough
- **Agent drift** — ignored constraints without justification
- **Tool mismatch** — PRD S12 not updated, agent guessed wrong
- **Security blindness** — agent didn't recognize security pattern
- **Underspecified test strategy** — TDD S7 didn't call out integration test requirements

---

## Step 5: Alignment Score

Score 1-10:

- 10: perfect adherence, all divergences justified
- 7-9: minor justified divergences
- 4-6: mix of justified + problematic
- 1-3: major problematic divergences

---

## Step 6: Write system-review.md

**Path:** `docs/features/{slug}/retrospective/system-review.md`

```markdown
# System Review: {slug}
**Date:** {ISO-date} | **Reviewer:** @review-agent (AI-Generated)
**Alignment Score:** {N}/10
**Execution Source:** JIRA_BREAKDOWN.md Execution Log
**TDD Reference:** {tdd_ref}

---

## Divergence Analysis

| # | Divergence | TDD Intent | Actual | Classification | Severity | Story |
|---|-----------|-----------|--------|----------------|----------|-------|
| 1 | {desc} | {TDD spec} | {actual} | Justified/Problematic | CRITICAL/HIGH/MEDIUM/LOW | {STORY-ID} |

---

## Root Cause Analysis

**Divergence {N}: {title}**
- Why: {root cause}
- Impact: {effect on quality/security/architecture}
- Evidence: {Execution Log entry or review artifact ref}
- Fix Required: YES / NO
- Fix: {what to change, which file, TDD section ref}

---

## Actionable Findings (orchestrator dispatches these)

<!-- MACHINE-PARSEABLE: orchestrator reads this table to dispatch fixes -->

| # | Story | Severity | Description | Fix Instructions |
|---|-------|----------|-------------|-----------------|
| 1 | {STORY-ID} | CRITICAL/HIGH | {what's wrong} | {what to fix} |

Only Problematic + CRITICAL/HIGH here. Justified + MEDIUM/LOW = informational only.

---

## Informational Findings

| # | Divergence | Classification | Severity | Notes |
|---|-----------|----------------|----------|-------|
| 1 | {desc} | Justified/Problematic | MEDIUM/LOW | {context} |

---

## Pipeline Improvements (write back to actual files)

### Skill Updates
- `implement/SKILL.md`: {specific change to add}
- `security-scan/SKILL.md`: {specific change}
- `review-code/SKILL.md`: {specific change}

### Agent Updates
- `.claude/agents/developer.md`: {constraint to add}
- `.claude/agents/review-agent.md`: {pattern to add}

### TDD Guidance (for next feature)
- {TDD section that needs more detail}
- {Pattern that should be documented}

---

## Summary

**Total Divergences:** {N}
**Justified:** {N} ({%})
**Problematic:** {N} ({%})
**Actionable (CRITICAL/HIGH):** {N}
**Alignment Score:** {N}/10
**Pipeline Health:** Healthy | Needs Attention | Critical

**Key Findings:**
- {finding 1 with impact}
- {finding 2 with impact}
```

---

## Step 7: Propose Pipeline Improvements

After writing system-review.md, populate the Pipeline Improvements section with specific, actionable changes.

**Do NOT auto-apply changes to skill or agent files.** Present proposed changes to human:

```
AskUserQuestion({
  "questions": [{
    "header": "Apply improvements?",
    "question": "System review found {N} pipeline improvements. Apply to skill/agent files?",
    "multiSelect": false,
    "options": [
      {"label": "Yes — apply all", "description": "Updates skill/agent files with proposed changes"},
      {"label": "Review first",    "description": "Show diff of each change before applying"},
      {"label": "Skip",           "description": "Keep improvements in system-review.md only"}
    ]
  }]
})
```

Only apply after explicit human approval. On approval: read target file, apply specific change, write back.

---

## Step 8: Return to Orchestrator

```
0 actionable findings:
  → PASS. Proceed to PR creation.
  → Report: docs/features/{slug}/retrospective/system-review.md
  → Alignment: {N}/10

N actionable findings:
  → FINDINGS. {N} stories need fixes.
  → Actionable table populated — orchestrator dispatches.
  → Report: docs/features/{slug}/retrospective/system-review.md
```

---

## Prerequisites

- JIRA_BREAKDOWN.md Execution Log populated
- All stories ✅ COMPLETE or ⚪ DEFERRED
- TDD*.md exists
- At least some review artifacts exist

---

## Constraints

- Process audit only — not code review
- Actionable findings = Problematic + CRITICAL/HIGH only
- Justified divergences = informational, never block
- Pipeline improvements must be specific and actionable — not vague
- Apply improvements to actual files — not just document them
