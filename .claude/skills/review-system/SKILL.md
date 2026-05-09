---
name: review-system
description: "Subagent phase E of /execute. Spawned with fresh context after all stories complete. Pre-PR process audit — TDD design vs actual execution. Classifies divergences, root-cause analyzes, generates actionable findings + pipeline improvements. One-shot."
argument-hint: <feature-slug>
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Review System

Concise throughout. Fragments OK. → for causality. Tables over prose. Code/paths exact.

**Agents:** `release-agent`, `review-agent` (subagent)

Compare what was designed vs what was built. Find process bugs, not code bugs.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

---

## Step 0: Context Fence (Pre-Spawn)

Before spawning review subagent, verify orchestrator context does NOT contain:
- Implementation files (`*.java`, `*.ts`, `*.go`, `*.py` that are not test files)
- developer.md agent output
- implement/SKILL.md execution traces

If any present: summarise to `Implementation complete for {STORY-KEY}`, then discard.

---

## Input (from orchestrator)

| Field | Source |
|---|---|
| `slug` | feature slug |
| `execution_log` | JIRA_BREAKDOWN.md Execution Log section |
| `tdd_ref` | path to TDD*.md or IMPLEMENTATION_BRIEF.md |
| `prd_repos` | PRD Repos section or repo info from JIRA_BREAKDOWN.md |
| `review_artifacts` | paths to all execution/reviews/*.md files |

---

## Step 1: Read Context (single pass)

Read by heading, extract, discard raw content before next file:

1. `JIRA_BREAKDOWN.md` — grep `## Execution Log` heading, read that section only via offset/limit
2. `TDD*.md` — read section-by-section via heading grep + offset/limit. Discard raw content after extracting findings per section. IMPLEMENTATION_BRIEF.md → full file (short by design)
3. `PRD.md` — grep `## Repos` heading, read that section only
4. `story-summaries.md` — read first; load individual `execution/reviews/*.md` only for FINDINGS/REJECTED-BUG stories

No re-reads. Hold at most 1 extracted section in context.

---

## Step 2: Adherence Analysis

Per story in Execution Log, check:

| Question | Signal if No |
|---|---|
| Implementation matches TDD interfaces + component design? | arch drift |
| Repeated failures at same phase? | TDD gap or agent drift |
| Security-scan found issues TDD should have prevented? | TDD security gap |
| QA rejected for bugs TDD test strategy should have caught? | underspecified test strategy |
| TDD deviations flagged in review artifacts? | agent drift |
| Correct build tool + test runner per PRD Repos section? | stack non-compliance |

---

## Step 3: Divergence Classification

| Class | Criteria |
|---|---|
| Justified | TDD incomplete, agent adapted correctly; agent used PRD Repos tools over TDD assumption; agent followed codebase convention not in TDD |
| Problematic | Invented components not in TDD; skipped required tests; security constraint violated; ignored PRD Repos tool specs |

---

## Step 4: Root Cause Analysis

Per divergence, assign one root cause:

| Root Cause | Meaning |
|---|---|
| TDD incompleteness | Section didn't specify clearly enough |
| Agent drift | Ignored constraints without justification |
| Tool mismatch | PRD Repos not updated, agent guessed wrong |
| Security blindness | Agent didn't recognize security pattern |
| Underspecified test strategy | TDD S7 didn't call out integration test requirements |

---

## Step 5: Alignment Score

| Score | Meaning |
|---|---|
| 10 | Perfect adherence, all divergences justified |
| 7–9 | Minor justified divergences |
| 4–6 | Mix of justified + problematic |
| 1–3 | Major problematic divergences |

---

## Step 6: Write system-review.md

Load: `.claude/skills/review-system/references/system-review-template.md`

Write to: `docs/features/{project}/{slug}/retrospective/system-review.md`

---

## Step 7: Propose Pipeline Improvements

Populate Pipeline Improvements section. Never auto-apply.

AskUserQuestion: "System review found {N} pipeline improvements. Apply to skill/agent files?"
Options: Apply all | Review first (show diffs) | Skip (keep in system-review.md only)

On approval: read target file, apply specific change, write back.

---

## Step 8: SubagentStop Validation

system-review.md MUST contain before returning:

| Check | Requirement |
|---|---|
| Analysis depth | ≥10 lines of analysis per COMPLETE story (headings/blank lines/table rows excluded) |
| Divergence Analysis table | Present (may be empty) |
| Actionable Findings table | Present (may be empty) |
| TDD vs implementation comparison | Present |

If any check fails: do NOT pass gate, do NOT return to orchestrator, do NOT retry. Escalate:
```
System review appears incomplete — minimum analysis threshold not met for story {KEY}.
Expected ≥10 lines of analysis per story, found {N} lines total.
This is a process audit failure, not a feature failure.
```

Empty Actionable Findings table + all checks passed = PASS.

---

## Step 9: Return to Orchestrator

**0 actionable findings:**
```
→ PASS. Proceed to PR creation.
→ Report: docs/features/{project}/{slug}/retrospective/system-review.md
→ Alignment: {N}/10
```

**{N} actionable findings — MANDATORY human approval before dispatching fixes:**

AskUserQuestion: "System review found {N} actionable divergence(s). [Top 3: story key + summary]"
Options: Apply all fixes → dispatch /implement | Review first → open file, re-ask | Skip → mark ACCEPTED_DIVERGENCE, proceed to PR

---

## Prerequisites

- JIRA_BREAKDOWN.md Execution Log populated
- All stories COMPLETE or DEFERRED
- TDD*.md or IMPLEMENTATION_BRIEF.md exists
- At least some review artifacts exist

---

## Constraints

- Process audit only — not code review
- Actionable findings = Problematic + CRITICAL/HIGH only
- Justified divergences = informational, never block
- Pipeline improvements must be specific and actionable
- Never auto-apply changes to skill/agent files
