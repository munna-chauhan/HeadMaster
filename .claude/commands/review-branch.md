---
name: review-branch
description: "Standalone branch review against base. Checks code quality, security, logic across all commits. No pipeline context required."
argument-hint: [branch] [--base <base-branch>]
---

# /review-branch

Review all changes on a branch vs base. Standalone — no pipeline, no TDD, no story context.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

## Arguments

- `$1` — branch to review (optional, default: current branch)
- `--base` — base branch (optional, default: `main`)

## Steps

### 1. Gather diff

```bash
BRANCH=${1:-$(git branch --show-current)}
BASE=${base:-main}
git log ${BASE}..${BRANCH} --oneline
git diff ${BASE}...${BRANCH} --stat
git diff ${BASE}...${BRANCH}
```

No commits ahead → "Branch is up to date with {BASE}. Nothing to review." Stop.

If >500 lines → read diff in file groups (by directory/module), summarize each before findings.

### 2. Classify change type

Infer from branch name + diff content (same table as `/review-pr`).

### 3. Review

Load `.claude/agents/review-agent.md` constraints. Agent methodology governs.

Same check matrix as `/review-pr`. Confidence ≥80. Diff-only.

**Additional branch-specific checks:**
- Commit hygiene: atomic commits? Meaningful messages? No fixup/WIP left?
- Merge readiness: conflicts with base? Build passes?

### 4. Build check

Detect build tool → run on branch:
```bash
git checkout ${BRANCH}
{build_cmd}
```

Build fail → flag as BLOCKER.

### 5. Output

```markdown
## Branch Review: {branch} → {base}

**Commits:** {N} | **Size:** +{N}/-{N} | **Files:** {N}

### Commit Log
{oneline log}

### Findings
`{file}:L{line}: [{SEVERITY}] {problem}. {fix}.`

### Build
{PASS | FAIL: error summary}

### Summary
Critical: {N} | High: {N} | Medium: {N} | Low: {N}

**Verdict:** {PASS | FINDINGS | BLOCKED}
**Merge-ready:** {Yes | No — reason}
```
