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
tdd_section,   ← S3+S4+S5+S6+S7 for this repo only
attempt,       ← 1=fresh, >1=retry
failure_ctx    ← delta from prior failure (null if attempt=1)
```

Read `memory/features/{slug}/agents/developer.md` if exists.

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

## Return

```
PASS: branch, files, tests added, build GREEN
FAIL: reason, what tried, what needed
```

## Constraints

- One story, one repo — never touch files outside assigned repo
- TDD = blueprint — implement exactly, flag `[TDD GAP]` never invent
- No gold-plating — only what ACs require
- Retry: never repeat same approach
