# Story Loop (Sequential)

For each story in dependency order:

## 4a. Back-merge check

```bash
NEW=$(git log feature/{slug}..origin/{MAIN} --oneline)
[ -n "$NEW" ] && git checkout feature/{slug} && git merge origin/{MAIN} --no-ff
```

## 4b. Update status

```
JIRA_BREAKDOWN.md: Status → 🔄 IN PROGRESS
TaskUpdate: [EXEC] {LOCAL-ID} → in_progress
```

```bash
python3 scripts/metrics.py emit {slug} story_start --phase execute --stage implement --story {STORY-KEY}
```

---

## Phase A: Implement

Run per `.claude/skills/implement/SKILL.md`.

- PASS → proceed to Phase B
- FAIL → attempt += 1. If attempt >= max_loops → ESCALATE

**After phase A:** `/handoff`

---

## Phase B: Security Scan

Run per `.claude/skills/security-scan/SKILL.md`.

```
JIRA_BREAKDOWN.md: Status → 🔍 SCANNING
```

- PASS / WARNING → proceed to Phase C
- BLOCKED → back to Phase A

**After phase B:** `/handoff`

---

## Phase C: Review Code

Run per `.claude/skills/review-code/SKILL.md`. Spawn `review-agent` as isolated subagent (fresh context).

**Before spawning:** `/handoff` (clears parent context)

```
JIRA_BREAKDOWN.md: Status → 👁️ IN REVIEW
```

- PASS → proceed to Phase D
- FINDINGS (critical/high) → back to Phase A
- attempt >= max_loops → ESCALATE

**After phase C:** `/handoff`

---

## Phase D: QA Integration

Run per `.claude/skills/qa-integration/SKILL.md`. Spawn `qa-engineer` as isolated subagent (fresh context).

**Before spawning:** `/handoff` (clears parent context)

```
JIRA_BREAKDOWN.md: Status → 🧪 IN QA
```

- APPROVED → story complete
- APPROVED_PARTIAL → story complete (deferred ACs surfaced in system-review and PR)
- REJECTED-BUG → back to Phase A
- attempt >= max_loops → ESCALATE

**After phase D:** `/handoff`

---

## Story Complete

```
JIRA_BREAKDOWN.md: Status → ✅ COMPLETE
TaskUpdate: [EXEC] {LOCAL-ID} → completed
Jira: transition → Done (if jira_push)
```

```bash
python3 scripts/metrics.py emit {slug} story_complete --phase execute --stage complete --story {STORY-KEY} --verdict PASS
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
