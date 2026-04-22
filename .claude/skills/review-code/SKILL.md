---
name: review-code
description: "Subagent phase C of /execute. Spawned with fresh context — no implementation memory. Reviews git diff only — TDD compliance, OWASP gaps, logic. 80+ confidence. Never fixes."
argument-hint: <story-key> <slug> <branch> <base> <repo-path>
---

# Review Code

Load `.claude/agents/review-agent.md` constraints.

Spawned as isolated subagent — no shared context with implementer. Review git diff only. **80+ confidence before
flagging. Never fix.**

---

## Step 1: Get diff

```bash
cd {repo_path}
git diff {base_branch}...story/{STORY-KEY}
```

No diff → PASS immediately.

Read `memory/features/{slug}/agents/review-agent.md` if exists.

---

## Step 2: Review diff

**TDD compliance** (use cached tdd_section — S3+S4 only):

- Interface signatures match exactly
- No invented components
- No gold-plating

**Security — OWASP Top 10 coverage (full list in review-agent.md)**

**Logic + quality:**

- Null/empty checks missing
- Silent exception swallowing → CRITICAL
- Resource leaks
- N+1 queries, unbounded results
- Pattern consistency with codebase

**Confidence filter:** 80+ only. Verify before flagging. No pre-existing issues in unchanged code.

---

## Step 3: Write report

**Path:** `docs/features/{slug}/execution/reviews/code-review-{STORY-KEY}.md`

```markdown
# Code Review: {STORY-KEY}
Verdict: {PASS|FINDINGS|BLOCKED} | {ISO-datetime}
Diff: +{N}/-{N} lines

## TDD Compliance
{PASS | deviations with section ref}

## Security (OWASP Top 10)
{PASS | file:line + issue + fix}

## Logic + Quality
### [{SEVERITY}] {title}
File: {path}:{line} | Confidence: {N}%
Issue: {description}
Fix: {concrete suggestion}

## Summary
Critical: {N} | High: {N} | Medium: {N} | Low: {N}
```

---

## Step 4: Update memory

`memory/features/{slug}/agents/review-agent.md` (max 200 words):

- Patterns found, recurring issues, what fixed on retry

---

## Verdict

| Finding               | Verdict  |
|-----------------------|----------|
| 0 critical, 0 high    | PASS     |
| critical/high present | FINDINGS |
| secrets/CVE           | BLOCKED  |

FINDINGS → return to implement with blocking findings only.
