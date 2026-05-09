# Finalize

## Step 5: Escalation

Triggered at attempt >= max_loops or merge conflict.

**Load failure ledger for escalation context:**

```bash
python scripts/failure_ledger.py load {slug} {STORY-KEY}
```

Include the full ledger output in the escalation report so the human sees all attempted approaches.

```bash
python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} fail "{reason}"
```

Write: `docs/features/{project}/{slug}/execution/reviews/escalation-{STORY-KEY}.md`

Escalation report MUST include:
- All attempted approaches (from ledger)
- Error for each attempt
- Hypothesis for each failure
- Files touched across all attempts

Ask per `.claude/agents/references/ask-user-protocol.md` — topic: "Story {STORY-KEY} escalation: choose next action."

Options:
- **Reset + retry** — clear failure ledger, re-run story from Phase A
- **Fix manually** — re-run `/execute {slug} --story {STORY-KEY}` when done
- **Skip (defer)** — `python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} defer "escalated"`
- **Stop** — halt execution, leave state as-is

---

## Step 6: System Review (isolated subagent after all stories)

**Before starting system review, log phase entry:**
```bash
python scripts/run_logger.py {project} {slug} "Execute/Phase E" "PHASE_START" "Starting system-level review after all stories complete" "HIGH"
```

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
- docs/features/{project}/{slug}/execution/story-summaries.md — primary source (read first)
- docs/features/{project}/{slug}/breakdown/JIRA_BREAKDOWN*.md — Execution Log section ONLY (do not load full file)
- docs/features/{project}/{slug}/design/TDD*.md — read section-by-section via heading grep, discard after extracting findings. IMPLEMENTATION_BRIEF.md → full file (short by design)
- docs/features/{project}/{slug}/planning/PRD.md — Repos section only (if exists)
- Individual review artifacts ONLY for stories flagged as FINDINGS/REJECTED-BUG in story-summaries.md:
    {flagged_review_paths}
  Do NOT load review artifacts for PASS stories.

Write: docs/features/{project}/{slug}/retrospective/system-review.md

Return:
  0 actionable findings → PASS
  N actionable findings → FINDINGS (list affected stories + severity)"
```

Before spawning: populate `{flagged_review_paths}` by scanning story-summaries.md for stories where `C=FINDINGS|BLOCKED` or `D=REJECTED-BUG`. List only those `execution/reviews/code-review-{KEY}.md` and `execution/reviews/qa-report-{KEY}.md` paths.

**On subagent return:**

0 actionable findings → update pipeline state + proceed to Step 6.5:
```bash
python scripts/gate_transition.py {project} {slug} execute complete --artifact docs/features/{project}/{slug}/retrospective/system-review.md
```
N actionable → re-dispatch affected stories through full phase cycle.

---

## Step 6.5: Pre-PR Security Gate

Two sequential scans on full feature diff. Both must pass before PR creation.

| # | Command | Catches |
|---|---------|---------|
| 1 | `python scripts/security_prescan.py --project {project} --feature {slug} --diff-target {MAIN} --quiet` | Secrets, SAST, dependency CVEs |
| 2 | `/scan diff --pr` | OWASP scan, cross-story regressions, merge-introduced issues |

**Exit 0:** proceed. **Exit 1 (BLOCKED):** halt — AskUserQuestion: fix + re-run / review + proceed / stop.

Report: `.security/SECURITY_REPORT.md`

---

## Step 6.8: Branch Roll-up (if epic/child-epic branches exist)

Merge intermediate branches up to `feature/{slug}` before PR. Skip if no epic branches were created in setup Step 4.

```bash
# Child-epic → epic (per child-epic branch)
git checkout epic/{EPIC-KEY} && git merge --no-ff child-epic/{CHILD-KEY} -m "merge: {CHILD-KEY} into epic/{EPIC-KEY}"

# Epic → feature
git checkout feature/{slug} && git merge --no-ff epic/{EPIC-KEY} -m "merge: {EPIC-KEY} into feature/{slug}"

# Push feature
git push origin feature/{slug}

# Cleanup intermediate branches
git branch -d child-epic/{CHILD-KEY} && git push origin --delete child-epic/{CHILD-KEY}
git branch -d epic/{EPIC-KEY} && git push origin --delete epic/{EPIC-KEY}
```

If merge conflict at any level → escalate, do not auto-resolve.

---

## Step 7: PR

```bash
/create-pr feature/{slug} {MAIN}
```
