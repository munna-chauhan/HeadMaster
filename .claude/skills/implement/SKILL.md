---
name: implement
description: "Inline phase A of /execute. Implements one story — tests first, atomic commits, build green."
argument-hint: <story-key> <slug>
---

# Implement

Load `.claude/agents/developer.md` constraints.

One story. One repo. Tests first. Build green.

---

## Context (from execute — already cached, no file reads)

```
story_id, title, acs[], dev_notes,
repo, repo_path, build_cmd, parent_branch,
tdd_section,   ← S3+S4+S5+S6+S7 for this repo only (OR full IMPLEMENTATION_BRIEF.md for lite tier)
attempt,       ← 1=fresh, >1=retry
failure_ctx    ← structured ledger from failure_ledger.py (null if attempt=1)
```

Read `memory/features/{slug}/agents/developer.md` if exists.

**If attempt > 1 — load failure ledger (mandatory before any code changes):**

```bash
python3 scripts/failure_ledger.py load {slug} {STORY-KEY}
```

This returns JSON with all prior failure records and an `excluded_approaches` list.
You MUST read every entry in `excluded_approaches` and plan an approach that is structurally different.
If your planned approach has >70% word overlap with any excluded approach, choose a different strategy.

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

**4. Write memory** `memory/features/{slug}/agents/developer.md` (max 200 words)

- Files touched, patterns found, retry history

---

## On Failure — Record to Ledger (mandatory before returning FAIL)

```bash
python3 scripts/failure_ledger.py append {slug} {STORY-KEY} --record '{
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
- Retry: load failure ledger, read excluded_approaches, implement structurally different approach
- Never start coding on retry without first reading the full failure ledger output
