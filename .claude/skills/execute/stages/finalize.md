# Finalize

## Step 5: Escalation

Triggered at attempt >= max_loops or merge conflict.

**Load failure ledger for escalation context:**

```bash
sh scripts/failure_ledger.py load {slug} {STORY-KEY}
```

Include the full ledger output in the escalation report so the human sees all attempted approaches.

```bash
sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} fail "{reason}"
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
- **Skip (defer)** — `sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} defer "escalated"`
- **Stop** — halt execution, leave state as-is

---

## Step 6: Phase C — System Review + Integration QA (after all stories complete)

```bash
sh scripts/run_logger.py {project} {slug} "Execute/Phase C" "PHASE_START" "Starting Phase C: system review + integration QA" "HIGH"
```

**Subagent failure policy (Phase C only):**

| Output | Action |
|--------|--------|
| Success verdict | Proceed |
| NEEDS_CONTEXT | Retry once with missing context |
| BLOCKED / empty / <50 chars | Retry once |
| Retry fails | Escalate to human |
| 529 error | Wait 30s, retry once |

Spawn two subagents in parallel — isolated context, no per-story history:

---

**Subagent 1 — System Review:**
```
Agent: review-agent
Model: sonnet
Prompt:
"Load .claude/skills/review-system/SKILL.md and execute fully.

slug: {slug}
story-summaries: docs/features/{project}/{slug}/execution/story-summaries.md
TDD: docs/features/{project}/{slug}/design/TDD*.md or IMPLEMENTATION_BRIEF.md
PRD Repos section: docs/features/{project}/{slug}/planning/PRD.md — Repos heading only
No per-story review artifacts exist.

Write: docs/features/{project}/{slug}/retrospective/system-review.md
Return: PASS | FINDINGS (list affected stories + severity)"
```

**Subagent 2 — Integration QA:**

Before spawning, extract TDD S7 (test strategy) by heading grep, cap 2000 chars — pass inline:
```bash
python -c "
import re
from pathlib import Path
tdd = next(Path('docs/features/{project}/{slug}/design').glob('TDD*.md'), None) \
      or Path('docs/features/{project}/{slug}/design/IMPLEMENTATION_BRIEF.md')
text = tdd.read_text() if tdd and tdd.exists() else ''
s = re.findall(r'(?m)^#{1,2}\s+(?:S7|Test Strategy|Testing).*?(?=^#{1,2}\s|\Z)', text, re.DOTALL)
print('\n'.join(s)[:2000])
"
```

Also flatten all story ACs from cached setup data — one line per AC: `{KEY}|AC-{N}|{text}`.

```
Agent: qa-engineer
Model: sonnet
Prompt:
"Phase C integration QA for feature {slug}.

Repo: {repo_path} | Branch: feature/{slug} | Build: {build_cmd}

All story ACs:
{all_acs_block}

TDD test strategy:
{tdd_s7_extract}

Steps:
1. git checkout feature/{slug}
2. Run .claude/skills/qa-integration/scripts/test_infra_detector.py — classify each AC
3. Run developer tests — verify they pass on feature/{slug}
4. For ACs not covered by developer tests: write integration tests
5. Run full test suite — report regressions
6. Commit new tests to feature/{slug}

Write: docs/features/{project}/{slug}/retrospective/qa-report.md
Verdict: APPROVED | APPROVED_PARTIAL | REJECTED-BUG"
```

---

**Parse verdicts from subagent output files:**
```bash
REVIEW_VERDICT=$(sh scripts/parse_verdict.py \
  docs/features/{project}/{slug}/retrospective/system-review.md "PASS,FINDINGS")
QA_VERDICT=$(sh scripts/parse_verdict.py \
  docs/features/{project}/{slug}/retrospective/qa-report.md "APPROVED,APPROVED_PARTIAL,REJECTED-BUG")
```

**Combined gate:**

| System Review | QA | Action |
|---------------|----|--------|
| PASS | APPROVED | Proceed to Step 6.5 |
| PASS | APPROVED_PARTIAL | Proceed (NOT_VERIFIABLE noted) |
| FINDINGS (MEDIUM/LOW only) | APPROVED or APPROVED_PARTIAL | Proceed — non-blocking |
| FINDINGS (CRITICAL/HIGH) | any | Escalate |
| any | REJECTED-BUG | Escalate |
| error / retry exhausted | any | Escalate — subagent context/timeout issue |

**On escalation — AskUserQuestion per `.claude/agents/references/ask-user-protocol.md`:**
- Topic: "Phase C: {N} blocking findings before PR."
- Include: finding summaries from both reports.
- Options: Fix in-place on feature/{slug} / Re-dispatch affected story / Accept and proceed / Stop

After fix → re-run Phase C once. If blocking findings persist → hard stop (AskUserQuestion: accept risk / stop).

```bash
sh scripts/gate_transition.py {project} {slug} execute complete --artifact docs/features/{project}/{slug}/retrospective/system-review.md
```

---

## Step 6.5: Pre-PR Security Gate

Two sequential scans on full feature diff. Both must pass before PR creation.

| # | Command | Catches |
|---|---------|---------|
| 1 | `sh scripts/security_prescan.py --project {project} --feature {slug} --diff-target {MAIN} --quiet` | Secrets, SAST, dependency CVEs |
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
