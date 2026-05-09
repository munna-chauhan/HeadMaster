---
name: commit
description: Atomic git commit with conventional message, secret scanning, and story traceability.
argument-hint: [files]
---

# /commit

Create a single atomic commit. Conventional Commits format. Secret scan before commit.

## Arguments

- `$1` — files to commit (optional, default: all staged or unstaged changes)

## Commit Message Format

`<type>(<scope>): <description>`

| Type | Use |
|---|---|
| feat | New feature |
| fix | Bug fix |
| docs | Documentation |
| style | Formatting only |
| refactor | Refactoring |
| test | Tests |
| chore | Build/config |

**Rules:**
- Imperative present tense ("add" not "added")
- Subject < 50 chars, lowercase, no trailing period
- Body (optional): blank line after subject, bulleted details
- Trailer (optional): `Implements: STORY-KEY AC-N` and `Refs: TDD Section X.Y`
- NEVER mention "Claude", "AI", "Anthropic", or "Co-authored-by"

## Steps

### 1. Review diff

```
git diff --cached
git diff
```

If diff contains unrelated changes → STOP, ask user to split.

### 2. Stage

```
git add <files>
```

Verify staged:
```
git diff --cached --quiet
```
If nothing staged → report "Nothing staged" and stop.

### 3. Idempotency check

```
git log -1 --oneline
```

If last commit message matches the intended message → STOP, report "Already committed".

### 4. Secret scan

```
python scripts/secret_scanner.py --staged
```

If secrets detected → STOP. Report findings. Do not commit.

### 5. Dry-run check

If `pipeline.dry_run: true` in config.yml → log "DRY-RUN: would commit with message: {msg}" and stop. Do not commit.

### 6. Commit

```
git commit -m "<type>(<scope>): <description>"
```

With traceability:
```
git commit -m "<type>(<scope>): <description>

Implements: <STORY-KEY> AC-<N>
Refs: TDD <section>"
```

### 7. Report

```
Message: {exact message}
Status: {Success|Failure} — {short hash}
Files: {list}
```

## Rollback

```
git revert <hash>
```
