# Story Loop

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

Resolved once from `{setup}` — no per-story subprocess for these:
- `autonomous` — true|false (ambiguity + phase transitions)
- `max_loops` — retry limit
- `jira_push` — Jira transition on complete
- `tier` — xs|s|m|l (determines verify model)
- `token_budget` — `{setup.token_budget.review_max}`, `{setup.token_budget.qa_max}`

---

## Subagent Failure Policy

| Output | Action |
|--------|--------|
| Success verdict | Proceed |
| NEEDS_CONTEXT | Retry once with missing context |
| BLOCKED / empty / <50 chars | Retry once with phase-specific context |
| Retry fails | Escalate: phase + story key |
| 529 error | Wait 30s, retry once |

---

**Single story filter:** If `--story STORY-KEY` provided: process only that story. Skip Phase E after.

For each story (dependency order):

---

## Pre-story

```bash
# Back-merge check
NEW=$(git log feature/{slug}..origin/{MAIN} --oneline)
[ -n "$NEW" ] && git checkout feature/{slug} && git merge origin/{MAIN} --no-ff
```

If merge exit code != 0 (conflict):
- `python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} blocked "merge conflict"`
- Escalate: "Back-merge conflict on {STORY-KEY}. Resolve manually then re-run."
- **Do NOT proceed to Phase A.**

```bash
python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} start
```

---

## Story Type + Verify Mode

Before Phase A, infer story type and select the effective verify tier.

**Infer from** title prefix, AC keywords, dev_notes:

| Story type | Signals |
|------------|---------|
| `feature` | "add", "implement", "create", "introduce", new endpoints |
| `bug` | "fix", "resolve", "correct", "broken", "regression", "error" |
| `refactor` | "refactor", "clean", "rename", "extract" — no behavior change |
| `docs` / `chore` | docs, config, infra, dependency bump only |

**Effective verify tier** (overrides feature tier for this story only):

| Story type | Feature tier → Effective verify |
|------------|----------------------------------|
| `feature` | unchanged — use feature tier |
| `bug` | l → m combined · m → s combined · s/xs → xs inline |
| `refactor` | any → xs inline |
| `docs` / `chore` | any → **skip verify** |

Store as `{story_verify_tier}` and use in the Verify section below.

---

## Phase A: Implement + Scan

Run per `.claude/skills/implement/SKILL.md`. Security scan is the final step of implement (no separate Phase B).

**Ambiguity during implementation:**
- If `{autonomous}=true` → assume, log decision inline, continue
- If `{autonomous}=false` → AskUserQuestion with specific question

PASS → proceed to Verify.

FAIL (attempt < max_loops) → load failure ledger, retry with structurally different approach.

FAIL (attempt >= max_loops):
- If `{autonomous}=true` → defer story: `python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} defer "max_loops exceeded"`; continue to next story
- If `{autonomous}=false` → AskUserQuestion: Fix TDD / Fix Story / Defer Story

---

## Verify

Use `{story_verify_tier}` (set above) — not the raw feature tier. If story type is `docs`/`chore`, skip this section entirely.

> **Script arg rule:** `story_phase_complete.py` and `gate_transition.py` use POSITIONAL args only.
> Correct: `python scripts/story_phase_complete.py acme my-feature ACME-123 qa`
> Wrong: `python scripts/story_phase_complete.py --project acme --slug my-feature --story ACME-123 --phase qa`

### xs tier — inline verify (no subagent)

**Steps (inline, no subagent spawn):**
1. Run `{build_cmd}` → if exit != 0: FAIL
2. `git diff {base}...story/{STORY-KEY} --name-only` → confirm each AC keyword appears in at least one changed file
3. `git diff {base}...story/{STORY-KEY}` → scan ≤30 lines for hardcoded secrets, SQL/command injection patterns

**Verdicts:** PASS | FAIL (build broken or AC missing) | ESCALATE (security concern found)

PASS → story complete.
FAIL → back to Phase A. If attempt >= max_loops → escalate/defer.
ESCALATE → stop, surface finding before continuing.

### s tier — inline verify (no subagent)

No spawn — parent agent runs inline. Diff is small at s tier; parent can AskUserQuestion on ambiguous findings.

```bash
git diff {base}...story/{STORY-KEY}
```

1. **AC coverage** — each AC maps to ≥1 changed file. List uncovered ACs.
2. **Quick scan** — grep diff for hardcoded secrets, OWASP A01/A02/A03 (SQL concat, missing auth, plaintext creds). Confidence ≥80 only. Format: `file:L{n}: [SEV] problem. fix.`
3. **Build** — `{build_cmd}` → verify exit 0.
4. **Ambiguity** — unclear finding → AskUserQuestion before recording. Never assume.

**Verdicts:** PASS | FINDINGS (file:line) | REJECTED-BUG (build failed)

PASS → story complete.
FINDINGS or REJECTED-BUG → back to Phase A. If attempt >= max_loops → escalate/defer.

### m tier — combined verify (single Sonnet subagent)

```bash
python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} review
```

Spawn single subagent (`model: claude-sonnet-4-6`, `max_tokens: {token_budget.review_max + token_budget.qa_max}`).

**Context — assembled per story using `design_section` from loop_state.json:**

| `design_section` | TDD file | Sections to grep |
|-----------------|----------|-----------------|
| `null` | `IMPLEMENTATION_BRIEF.md` | Full file (short by design) |
| `"TDD"` | `design/TDD.md` | S3/S4 + S7 by heading only |
| `"{NAME}"` | `design/TDD_{NAME}.md` | S3/S4 + S7 by heading only |

```bash
# Extract sections by heading — never load full TDD
python -c "
import re, sys
from pathlib import Path
tdd = Path('{tdd_path}')
text = tdd.read_text()
# Extract S3, S4, S7 sections only
sections = re.findall(r'(?m)^#{1,2}\s+(?:S[347]|Section [347]|Interface|Test Strategy).*?(?=^#{1,2}\s|\Z)', text, re.DOTALL)
print('\n'.join(sections)[:3000])  # hard cap 3000 chars
"
```

**Prompt structure (cache-optimized — static prefix first):**
```
[STATIC PREFIX — cacheable across stories in same breakdown]
1. Agent definition constraints (review-agent.md + qa-engineer.md — agents bring own methodology)
2. Extracted TDD sections (≤3000 chars, same for all stories from same design_section)

[DYNAMIC — changes per story]
3. ACs for this story (from cached story data)
4. git diff for this story
```

**Task:**
1. **Review** — execute per `.claude/agents/review-agent.md`. Scope: enabled checks from PR type matrix.
2. **QA** — execute per `.claude/agents/qa-engineer.md`. Scope: this story's ACs only.

**Verdicts:** PASS | FINDINGS | MINOR_FINDINGS | REJECTED-BUG

PASS → story complete.
FINDINGS (critical/high severity) → back to Phase A. If attempt >= max_loops → escalate/defer.
MINOR_FINDINGS → **Targeted Fix** (see below). If attempt >= max_loops → escalate/defer.
REJECTED-BUG → back to Phase A. If attempt >= max_loops → escalate/defer.

**Targeted Fix (MINOR_FINDINGS only):**
Applies when ALL findings are severity LOW, no architectural change required, fix is ≤3 targeted edits.
1. Developer agent receives: diff + specific findings only (no full reimplementation context)
2. Makes targeted edits on same story branch
3. Returns directly to Phase C verify (skips Phase A rerun)
4. If targeted fix verify returns FINDINGS (any severity) → back to Phase A (full reimplementation)

### l tier — combined Phase C + D (single subagent)

```bash
python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} review
```

Spawn single subagent (`model: claude-sonnet-4-6`, `max_tokens: {token_budget.review_max + token_budget.qa_max}`).

**Context — same `design_section` resolution as m tier.** Same TDD extraction logic, same 3000-char cap.

**Prompt structure (cache-optimized):**
```
[STATIC PREFIX]
1. Agent definition constraints (review-agent.md + qa-engineer.md — agents bring own methodology)
2. OWASP checklist: `.claude/agents/references/owasp-checklist.md`
3. Extracted TDD sections (≤3000 chars)

[DYNAMIC]
4. ACs for this story
5. git diff for this story
```

**Task (sequential in single subagent):**
1. **Review (Phase C)** — execute per `.claude/agents/review-agent.md`. Write to `execution/reviews/code-review-{STORY-KEY}.md`.
2. **QA (Phase D)** — execute per `.claude/agents/qa-engineer.md`. Write to `execution/reviews/qa-report-{STORY-KEY}.md`.

**Verdicts:**
- Review PASS + QA APPROVED/APPROVED_PARTIAL → story complete.
- Review FINDINGS (critical/high) → check convergence:
  ```bash
  python scripts/convergence_check.py {project} {slug} review --max-loops {max_loops}
  ```
  - CONTINUE → back to Phase A
  - ESCALATE → if `{autonomous}=true` → accept risk, log, proceed to QA step; else AskUserQuestion
- Review MINOR_FINDINGS (all LOW, no arch change, ≤3 edits) → Targeted Fix:
  - Developer agent receives diff + specific findings only
  - Makes targeted edits, returns to Phase C verify only
  - If re-verify returns FINDINGS (any) → back to Phase A
- QA REJECTED-BUG → back to Phase A. If attempt >= max_loops → escalate/defer.

---

## Story Complete

```bash
python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} complete --phases A,C,D

# Auto-merge — TARGET = story's parent_branch (resolved in setup Step 4)
TARGET={parent_branch}
git checkout {TARGET} && git pull
git merge --no-ff story/{STORY-KEY} -m "merge: {STORY-KEY} into {TARGET}"
[ "{pipeline.dry_run}" != "true" ] && git push origin {TARGET}

# Post-merge build — ONLY if this is the last story for this repo_path
# (no remaining NEW or IN_PROGRESS stories targeting the same repo)
if last_story_in_repo:
    {build_cmd} || {
        git revert HEAD --no-edit && git push origin {TARGET}
        python scripts/story_phase_complete.py {project} {slug} {STORY-KEY} fail "post-merge build failed"
        # Escalate; do NOT continue to next story
    }

# Cleanup
python scripts/failure_ledger.py cleanup {project} {slug} {STORY-KEY}
git branch -d story/{STORY-KEY}
git push origin --delete story/{STORY-KEY}

# Jira (if jira_push)
# Transition story → Done
```

## Story Execution Summary

Append to `docs/features/{project}/{slug}/execution/story-summaries.md`:

```
## {STORY-KEY} | {ISO-date}
Phases: A={attempts} C={verdict} D={verdict}
Findings: {count, or "clean"}
Key: {1-line summary of blocking findings, or "none"}
```

---

## Phase Transition

```
if autonomous=true  → continue to next story automatically
if autonomous=false → stop: "Story {KEY} complete. /execute {slug} to continue."
```

After all stories: load `.claude/skills/execute/stages/finalize.md`.
