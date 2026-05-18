---
name: implement
description: "Inline phase A of /execute. Implements one story — tests first, atomic commits, build green."
argument-hint: <story-key> <slug>
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Implement

Load `.claude/agents/developer.md` constraints.

One story. One repo. Tests first. Build green.


---

## Context (from execute — already cached, no file reads)

```
story_id, title, acs[], dev_notes,
repo, repo_path, build_cmd, parent_branch,
tdd_section,   ← S3+S4 only (interfaces + data models) — never load S5/S6/S7 inline (OR full IMPLEMENTATION_BRIEF.md for xs tier)
attempt,       ← 1=fresh, >1=retry
failure_ctx    ← structured ledger from failure_ledger.py (null if attempt=1)
```

Read `memory/agents/developer/MEMORY.md` if exists.

**Retry protocol:**

On FAIL → append to failure ledger (see "On Failure" below) → increment attempt → retry if ≤ max_loops, escalate if exceeded.

On retry (attempt > 1), BEFORE any code changes:

```bash
sh scripts/failure_ledger.py load {project} {slug} {STORY-KEY} --last 2
```

Returns last 2 failure records + full `excluded_approaches` list. Plan a structurally different approach (>70% word overlap with any excluded → choose different strategy). Do NOT include earlier ledger records — `excluded_approaches` covers them.

---

## Steps

**1. Branch**

```bash
cd {repo_path}
# attempt=1: /create-branch {parent_branch} story {STORY-KEY}
# retry:     git checkout story/{STORY-KEY} && git pull
```

**2. Per AC: test → implement → validate → commit**

- Write test → confirm FAIL
- Implement minimum code → confirm PASS
- `/commit` with `Implements: {STORY-KEY} AC-{N}`

**3. Full build**

```bash
{build_cmd}
```

Fix sequence: type errors → lint → format → tests. Never return broken branch.

**4. Security scan (inline — no separate Phase B)**

```bash
sh .claude/skills/security-scan/scripts/diff_scanner.py \
  --branch story/{STORY-KEY} \
  --base {base_branch} \
  --repo {repo_path}
```

- BLOCKED (secret or CRITICAL CVE) → append to failure ledger, return FAIL with security findings
- WARNING → include in PASS return: `PASS (security warnings: {summary})`
- PASS or no files → proceed

**5. Write memory** `memory/agents/developer/MEMORY.md` (max 200 words)

- Files touched, patterns found, retry history

---

## On Failure — Record to Ledger (mandatory before returning FAIL)

```bash
sh scripts/failure_ledger.py append {slug} {STORY-KEY} --record '{
  "approach": "<one-line description of what you tried>",
  "error_type": "<build_failure|test_failure|lint_error|runtime_error>",
  "error_summary": "<exact error message, max 200 chars>",
  "files_touched": ["<list of files modified this attempt>"],
  "hypothesis": "<why you think it failed and what should be different next time>"
}'
```

This is non-negotiable. Every FAIL must produce a ledger entry BEFORE returning.

---

## Return

```
PASS: branch, files, tests added, build GREEN
FAIL: reason, what tried, what needed (ledger entry already written)
```

## Constraints

- One story, one repo — never touch files outside assigned repo
- TDD = blueprint — implement exactly, flag `[TDD GAP]` never invent
- No gold-plating — only what ACs require
