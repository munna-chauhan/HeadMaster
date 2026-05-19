# Story Loop

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

Resolved once from `{setup}` — no per-story subprocess for these:
- `autonomous` — true|false (ambiguity + phase transitions)
- `max_loops` — retry limit
- `jira_push` — Jira transition on complete

---

**Single story filter:** If `--story STORY-KEY` provided: process only that story. Skip Phase C after.

For each story (dependency order):

---

## Pre-story

```bash
# Back-merge check
NEW=$(git log feature/{slug}..origin/{MAIN} --oneline)
[ -n "$NEW" ] && git checkout feature/{slug} && git merge origin/{MAIN} --no-ff
```

If merge exit code != 0 (conflict):
- `sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} blocked "merge conflict"`
- Escalate: "Back-merge conflict on {STORY-KEY}. Resolve manually then re-run."
- **Do NOT proceed to Phase A.**

```bash
sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} start
```

---

## Phase A: Implement + Scan

Run per `.claude/skills/implement/SKILL.md`. Security scan is the final step of implement. Phase B (AC check) runs after implement returns PASS.

**Ambiguity during implementation:**
- If `{autonomous}=true` → assume, log decision inline, continue
- If `{autonomous}=false` → AskUserQuestion with specific question

PASS → checkpoint phase A, then Phase B:
```bash
sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} checkpoint --phase A
```

FAIL (attempt < max_loops) → load failure ledger, retry with structurally different approach.

FAIL (attempt >= max_loops):
- If `{autonomous}=true` → defer story: `sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} defer "max_loops exceeded"`; continue to next story
- If `{autonomous}=false` → AskUserQuestion: Fix TDD / Fix Story / Defer Story

---

## Phase B: AC Check (inline)

Parent agent — no subagent spawn.

```bash
git diff {base}...story/{STORY-KEY} --name-only
```

For each AC, confirm at least one changed file name or path maps to the AC's domain (endpoint, module, model, config).

PASS → story complete.
FAIL → append uncovered ACs to failure ledger before retrying:
```bash
sh scripts/failure_ledger.py append {slug} {STORY-KEY} --record '{
  "approach": "phase_b_ac_check",
  "error_type": "ac_coverage_gap",
  "error_summary": "Uncovered ACs: {AC-N, ...}",
  "files_touched": [],
  "hypothesis": "Implementation did not touch files for the listed ACs"
}'
```
Back to Phase A. If attempt >= max_loops → escalate/defer.

---

## Story Complete

```bash
sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} complete --phases A,B

# Recurring finding detection — write to developer MEMORY.md before ledger cleanup
sh scripts/recurring_finding_detector.py {project} {slug}

# Phase A/B learning extraction — write failure patterns before ledger cleanup
sh scripts/extract_phase_learnings.py {project} {slug} {STORY-KEY}

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
        sh scripts/story_phase_complete.py {project} {slug} {STORY-KEY} fail "post-merge build failed"
        # Escalate; do NOT continue to next story
    }

# Cleanup
sh scripts/failure_ledger.py cleanup {project} {slug} {STORY-KEY}
git branch -d story/{STORY-KEY}
git push origin --delete story/{STORY-KEY}

# Jira (if jira_push)
# Transition story → Done
```

## Story Execution Summary

Append to `docs/features/{project}/{slug}/execution/story-summaries.md`:

```
## {STORY-KEY} | {ISO-date}
A={attempts} B=PASS|FAIL(uncovered:{AC-N,...})
Key: {1-line summary, or "clean"}
```

---

## Phase Transition

```
if autonomous=true  → continue to next story automatically
if autonomous=false → stop: "Story {KEY} complete. /execute {slug} to continue."
```

After all stories: load `.claude/skills/execute/stages/finalize.md`.
