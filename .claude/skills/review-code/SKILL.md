---
name: review-code
description: "Subagent phase C of /execute. Spawned with fresh context — no implementation memory. Reviews git diff only — TDD compliance, OWASP gaps, logic. 80+ confidence. Never fixes."
argument-hint: <story-key> <slug> <branch> <base> <repo-path>
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Review Code

Load `.claude/agents/review-agent.md` constraints.

Spawned as isolated subagent — no shared context with implementer. Review git diff only. **80+ confidence before
flagging. Never fix.**

---

## Step 1: Detect PR Type

Classify PR from branch name + diff:

| Type | Signals |
|------|---------|
| feature | `feature/`, `feat/` branch; substantial new files |
| bug | `fix/`, `bugfix/` branch; targeted change to existing behavior |
| refactor | `refactor/`, `chore/` branch; no behavior change |
| docs | `docs/` branch; only `.md`/`.txt`/`.rst` changes |
| security | `security/`, `hotfix/` branch; OWASP-related changes |

Apply review matrix — skip disabled checks, note them in report header:

| Check           | feature | bug | refactor | docs | security |
|-----------------|---------|-----|----------|------|----------|
| Secret detection| ✓       | ✓   | ✓        | ✓    | ✓        |
| Dependency CVEs | ✓       | ✓   | ✓        | ✗    | ✓        |
| SAST            | ✓       | ✓   | ✓        | ✗    | ✓        |
| TDD compliance  | ✓       | ✓   | ✗        | ✗    | ✓        |
| OWASP Top 10    | ✓       | ✓   | ✗        | ✗    | ✓        |
| Wiring+isolation| ✓       | ✓   | ✓        | ✗    | ✓        |
| Logic + quality | ✓       | ✓   | ✓        | ✗    | ✓        |
| Performance     | ✓       | ✗   | ✓        | ✗    | ✗        |

---

## Step 2: Scope + get diff

```bash
cd {repo_path}
git diff {base_branch}...story/{STORY-KEY} --stat
```

- No changed files → PASS immediately.
- Only docs/config (`.md`, `.yml`, `.json`, `.txt`, `.properties`) → skip SAST, deps, OWASP; run secret detection only.
- >500 lines changed → read diff in module/file groups, summarize each group before findings.

```bash
git diff {base_branch}...story/{STORY-KEY}
```

Read `memory/agents/review-agent/MEMORY.md` if exists.

---

## Step 3: Review diff

Apply enabled checks from Step 1 matrix. Agent methodology governs — do not override.

**Scope inputs (pass to agent):**
- TDD section: `tdd_section` (S3+S4 cached) — for TDD compliance check
- OWASP checklist: `.claude/agents/references/owasp-checklist.md` — load only for feature/bug/security types
- Diff target: only ADDED or MODIFIED lines in scope

Agent executes review per `.claude/agents/review-agent.md` — confidence thresholds, severity classification, finding format, and diff-only rule defined there. Skill does not restate.

---

## Step 4: Write report

**Path:** `docs/features/{project}/{slug}/execution/reviews/code-review-{STORY-KEY}.md`

```markdown
# Code Review: {STORY-KEY}
Verdict: {PASS|FINDINGS|BLOCKED} | {ISO-datetime}
Diff: +{N}/-{N} lines

## TDD Compliance
{PASS | deviations with section ref}

## Security (OWASP Top 10)
{PASS | file:line + issue + fix}

## Logic + Quality
`{file}:L{line}: [{SEVERITY}] {problem}. {fix}.`

## Summary
Critical: {N} | High: {N} | Medium: {N} | Low: {N}
```

---

## Step 5: Update memory

`memory/agents/review-agent/MEMORY.md` (max 200 words):

- Patterns found, recurring issues, what fixed on retry

---

## Verdict

| Finding               | Verdict  |
|-----------------------|----------|
| 0 critical, 0 high    | PASS     |
| critical/high present | FINDINGS |
| secrets/CVE           | BLOCKED  |

FINDINGS → return to implement with blocking findings only.
