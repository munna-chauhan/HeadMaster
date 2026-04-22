# Finalize

## Step 5: Escalation

Triggered at attempt >= max_loops or merge conflict.

**Load failure ledger for escalation context:**

```bash
python3 scripts/failure_ledger.py load {slug} {STORY-KEY}
```

Include the full ledger output in the escalation report so the human sees all attempted approaches.

```
JIRA_BREAKDOWN.md: Status → ❌ FAILED
Write: docs/features/{slug}/execution/reviews/escalation-{STORY-KEY}.md
```

Escalation report MUST include:
- All attempted approaches (from ledger)
- Error for each attempt
- Hypothesis for each failure
- Files touched across all attempts

```
AskUserQuestion({
  options: [
    "Reset + retry",
    "Fix manually — re-run /execute {slug} when done",
    "Skip (defer)",
    "Stop"
  ]
})
```

---

## Step 6: System Review (isolated subagent after all stories)

**Pattern:** Launch `review-agent` as isolated subagent for system-level audit. Fresh context — no per-story memory.

**Isolation:** Do NOT load execution history into parent context. Subagent reads TDD + git diff fresh.

**Spawn subagent:**

```
Agent: review-agent
Model: sonnet
Prompt:
"Load .claude/skills/review-system/SKILL.md and execute it fully.

Inputs:
- slug: {slug}
- JIRA_BREAKDOWN.md Execution Log section only
- TDD*.md or IMPLEMENTATION_BRIEF.md (search for divergences — do not hold full content)
- All execution/reviews/*.md artifacts
- PRD.md Repos section (if exists) or repo info from JIRA_BREAKDOWN.md

Write: docs/features/{slug}/retrospective/system-review.md

Return:
  0 actionable findings → PASS
  N actionable findings → FINDINGS (list affected stories + severity)"
```

**On subagent return:**

0 actionable findings → update pipeline state + proceed to PR:
```bash
python3 scripts/gate_transition.py {slug} execute complete --artifact docs/features/{slug}/retrospective/system-review.md
```
N actionable → re-dispatch affected stories through full phase cycle.

---

## Step 7: PR

```bash
/create-pr feature/{slug} {MAIN}
```
