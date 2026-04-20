---
name: execute
description: "Drives JIRA_BREAKDOWN.md stories to completion. Sequential inline phases per story: implement → scan → review → qa. /handoff+/clear between phases. Never writes code directly."
argument-hint: <feature-slug>
hooks:
  Stop:
    - hooks:
      - type: agent
        model: haiku
        timeout: 30
        prompt: |
          Check if execution is complete or legitimately paused.
          Extract slug from $ARGUMENTS.

          Read docs/features/{slug}/breakdown/JIRA_BREAKDOWN.md:
          1. Any stories IN PROGRESS / SCANNING / IN REVIEW / IN QA → ok to pause
          2. Any NEW stories with all blockers COMPLETE → work remains
          3. All COMPLETE or DEFERRED → check retrospective/system-review.md
          4. system-review.md exists → check for PR

          Check last_assistant_message:
          - Contains 'AskUserQuestion' → ok to pause
          - Contains 'ESCALATED' → ok to pause
          - Contains 'PR created' → complete

          Return {"ok": true} if complete or legitimately paused.
          Return {"ok": false, "reason": "<what remains>"} if work unfinished.
  PostToolUse:
    - matcher: "Bash"
      hooks:
      - type: prompt
        model: haiku
        timeout: 15
        prompt: |
          Bash command ran. Parse $ARGUMENTS as JSON.
          If command contains 'git merge' and exit code != 0:
            Return {"ok": false, "reason": "Merge failed — conflict. Escalate."}
          If command contains 'git push' and exit code != 0:
            Return {"ok": false, "reason": "Push failed. Check remote state."}
          All other: return {"ok": true}
---

# Execute

Load `.claude/agents/release-agent.md`. Read `config.yml`.

Mission: drive all stories to completion. Sequential inline phases. `/handoff`+`/clear` between each phase. **Never
write code.**

---

## Context Rules

- Load JIRA_BREAKDOWN.md once at init — extract story list, cache as text
- Load PRD S12 once — repo names, paths, build commands
- Never hold full TDD or PRD in context during execution
- Each phase reads only what it needs from disk

---

## Step 1: Initialize

**Validate:**

```
JIRA_BREAKDOWN.md exists + human-approved  → proceed
TDD*.md exists                             → proceed
PRD.md with PRD Status: APPROVED           → proceed
Missing → HALT with specific message
```

**Extract and cache (text only, not raw files):**

- Story list: id, title, ACs, dev_notes, repo, SP, status, blocked_by
- Repo map: name → path, build_cmd (from PRD S12)
- Config: max_loops, jira_push, parallel

**Register tasks:**

```
TaskCreate({title: "[EXEC] {LOCAL-ID}: {title}", status: "pending", ...})
```

---

## Step 2: Pre-flight (per unique repo)

```bash
cd {repo_path}
git status --porcelain | grep -q . && git stash save "execute-preflight-{slug}"
git fetch origin
MAIN=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')
git checkout $MAIN && git pull origin $MAIN
```

---

## Step 3: Branch Setup (per unique repo)

```bash
git show-ref --quiet refs/remotes/origin/feature/{slug} \
  && (git checkout feature/{slug} && git pull) \
  || /create-branch {MAIN} feature {slug}
```

---

## Step 4: Story Loop (sequential)

For each story in dependency order:

### 4a. Back-merge check

```bash
NEW=$(git log feature/{slug}..origin/{MAIN} --oneline)
[ -n "$NEW" ] && git checkout feature/{slug} && git merge origin/{MAIN} --no-ff
```

### 4b. Update status

```
JIRA_BREAKDOWN.md: Status → 🔄 IN PROGRESS
TaskUpdate: [EXEC] {LOCAL-ID} → in_progress
```

---

### Phase A: Implement

Load `.claude/agents/developer.md` constraints inline.

**Context (load once, discard after phase):**

- ACs from story
- TDD S3+S4+S5+S6+S7 for this repo only — search by section heading, do not read full TDD
- Dev Notes from story
- `memory/features/{slug}/agents/developer.md` if exists (retry context)

**Execute:**

1. Create branch: `/create-branch {parent} story {STORY-KEY}`
2. Per AC: write test (red) → implement (green) → validate → `/commit`
3. Full build: `{build_cmd}` — fix until green
4. Write memory: `memory/features/{slug}/agents/developer.md` (max 200 words)

**Result: PASS | FAIL**

- FAIL → attempt += 1. If attempt >= max_loops → ESCALATE
- Retry: read prior memory, do not repeat same approach

**After phase A — regardless of result:**

```
/handoff
```

*(handoff auto-runs /clear — context resets, phase state in memory)*

---

### Phase B: Security Scan

**Run Python scanner (mechanical — no Claude reasoning needed):**

```bash
python3 scripts/diff_scanner.py \
  --branch story/{STORY-KEY} \
  --base {parent_branch} \
  --repo {repo_path}
```

Read JSON output. Extract verdict, secrets, sast, deps.

**Verdict rules:**

- `BLOCKED` (secrets or CRITICAL CVE) → fix in implement, re-scan
- `WARNING` (HIGH SAST/dep) → log, proceed to review
- `PASS` → proceed

Write report: `docs/features/{slug}/execution/reviews/security-scan-{STORY-KEY}.md`

```
JIRA_BREAKDOWN.md: Status → 🔍 SCANNING
```

**After phase B:**

```
/handoff
```

---

### Phase C: Review Code

Load `.claude/agents/review-agent.md` constraints inline.

**Context (git diff only — no full file reads):**

```bash
cd {repo_path}
git diff {parent_branch}...story/{STORY-KEY}
```

Read the diff output directly. Do not read full changed files unless a specific line needs context.

**Review against:**

- ACs (from cached story data — no file read)
- TDD S3+S4 interfaces only (search by heading — do not read full TDD)

**Check:**

- TDD compliance: interfaces match, no gold-plating
- OWASP A01/A04/A05/A08 (A02/A03/A06/A07/A09/A10 covered by scanner)
- Logic: null checks, resource leaks, N+1, silent exceptions
- 80+ confidence before flagging

Write report: `docs/features/{slug}/execution/reviews/code-review-{STORY-KEY}.md`

**Verdict:**

- PASS (0 critical, 0 high) → proceed to QA
- FINDINGS (critical/high) → back to implement with findings
- attempt >= max_loops → ESCALATE

```
JIRA_BREAKDOWN.md: Status → 👁️ IN REVIEW
```

**After phase C:**

```
/handoff
```

---

### Phase D: QA Integration

Load `.claude/agents/qa-engineer.md` constraints inline.

**Context (load once):**

- ACs from cached story data
- TDD S7 test strategy only (search by heading)
- `memory/features/{slug}/agents/qa-engineer.md` if exists

**Execute:**

```bash
cd {repo_path}
git checkout story/{STORY-KEY} && git pull
{build_cmd}
```

Per AC: write integration test → run → evaluate.

- Own test wrong → fix, re-run (max 2 self-corrections)
- Code bug → REJECTED-BUG

Run regression: affected module only.

Write report: `docs/features/{slug}/execution/reviews/qa-report-{STORY-KEY}.md`

**Verdict:**

- APPROVED → story complete
- REJECTED-BUG → back to implement
- attempt >= max_loops → ESCALATE

```
JIRA_BREAKDOWN.md: Status → 🧪 IN QA
```

**After phase D:**

```
/handoff
```

---

### Story Complete

```
JIRA_BREAKDOWN.md: Status → ✅ COMPLETE
TaskUpdate: [EXEC] {LOCAL-ID} → completed
Jira: transition → Done (if jira_push)
```

**Auto-merge:**

```bash
TARGET=child-epic/{KEY} | epic/{KEY} | feature/{slug}
git checkout {TARGET} && git pull
git merge --no-ff story/{STORY-KEY} -m "merge: {STORY-KEY} into {TARGET}"
git push origin {TARGET}
git branch -d story/{STORY-KEY}
git push origin --delete story/{STORY-KEY}
```

---

## Step 5: Escalation

Triggered at attempt >= max_loops or merge conflict.

```
JIRA_BREAKDOWN.md: Status → ❌ FAILED
Write: docs/features/{slug}/execution/reviews/escalation-{STORY-KEY}.md
```

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

## Step 6: System Review (one-shot after all stories)

Load `.claude/skills/review-system/SKILL.md` inline.

Read:

- JIRA_BREAKDOWN.md Execution Log section only
- TDD*.md (search for divergences — do not hold full content)
- All `execution/reviews/*.md` artifacts

Write: `docs/features/{slug}/retrospective/system-review.md`

0 actionable findings → proceed to PR.
N actionable → re-dispatch affected stories through full phase cycle.

---

## Step 7: PR

```bash
/create-pr feature/{slug} {MAIN}
```

---

## Status Values

| Status         | Phase          |
|----------------|----------------|
| ⏳ NEW          | Not started    |
| 🔄 IN PROGRESS | implement      |
| 🔍 SCANNING    | security-scan  |
| 👁️ IN REVIEW  | review-code    |
| 🧪 IN QA       | qa-integration |
| ✅ COMPLETE     | Done           |
| ❌ FAILED       | Escalated      |
| ⚪ DEFERRED     | Skipped        |

---

## Prerequisites

- `docs/features/{slug}/breakdown/JIRA_BREAKDOWN.md` — human-approved
- `docs/features/{slug}/design/TDD*.md` — exists
- `docs/features/{slug}/planning/PRD.md` — PRD Status: APPROVED
