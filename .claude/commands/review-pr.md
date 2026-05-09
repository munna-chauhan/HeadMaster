---
name: review-pr
description: "Standalone PR review. Reads diff, checks quality, security, logic. No pipeline context required."
argument-hint: <pr-number-or-url> [--repo <owner/repo>]
---

# /review-pr

Review an existing PR. Standalone — no pipeline, no TDD, no story context.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

## Arguments

- `$1` — PR number or full GitHub URL
- `--repo` — owner/repo (optional, inferred from current git remote)

## Steps

### 1. Fetch PR

```bash
gh pr view {pr_number} --json title,body,baseRefName,headRefName,changedFiles,additions,deletions
gh pr diff {pr_number}
```

If >500 lines changed → read diff in file groups, summarize each before findings.

### 2. Classify PR type

| Type | Signals |
|------|---------|
| feature | substantial new files, new endpoints/components |
| bug | targeted fix to existing behavior |
| refactor | structural change, no behavior change |
| docs | only `.md`/`.txt`/config changes |
| security | auth/crypto/input-validation changes |

### 3. Review

Load `.claude/agents/review-agent.md` constraints. Agent methodology governs.

**Checks (enabled by PR type):**

| Check | feature | bug | refactor | docs | security |
|-------|---------|-----|----------|------|----------|
| Secret detection | all | all | all | all | all |
| SAST patterns | yes | yes | yes | no | yes |
| Logic + quality | yes | yes | yes | no | yes |
| Performance | yes | no | yes | no | no |

**Confidence ≥80 before flagging. Diff-only — never review unchanged code.**

### 4. Output

```markdown
## PR Review: #{number} — {title}

**Type:** {type} | **Size:** +{N}/-{N}

### Findings
`{file}:L{line}: [{SEVERITY}] {problem}. {fix}.`

### Summary
Critical: {N} | High: {N} | Medium: {N} | Low: {N}

**Verdict:** {PASS | FINDINGS | BLOCKED}
```

### 5. Post as comment (optional)

If user confirms → post review as PR comment:
```bash
gh pr review {pr_number} --comment --body-file {review_path}
```
