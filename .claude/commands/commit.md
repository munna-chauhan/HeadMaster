---
name: commit
type: command
description: Generate an atomic git commit with a standardized conventional commit message, secret scanning, and optional story/TDD traceability.
argument-hint: [files]
---

# Create Git Commit

**Target Files:** ${1:-"All uncommitted changes"}

## Objective

Create a single, logical, and "atomic" commit. The commit message must follow the Conventional Commits specification and
be descriptive enough to stand alone in the project history.

## Commit Message Format

- **Pattern:** `<type>(<scope>): <description>`
- **Types:**
    - `feat` (new feature)
    - `fix` (bug fix)
    - `docs` (documentation)
    - `style` (formatting, missing semi-colons, etc; no code change)
    - `refactor` (refactoring production code)
    - `test` (adding missing tests, refactoring tests)
    - `chore` (updating build tasks, package manager configs, etc)
- **Tense:** Use **imperative present tense** ("add" instead of "added" or "adds").
- **Constraints:**
    - Subject line: **< 50 characters**, lowercase, no trailing period.
    - Body (optional): blank line after subject, then bulleted details.
    - Trailer (optional): `Implements:`, `Refs:` lines for traceability.
- **Strict Privacy:** NEVER mention "Claude", "AI", "Anthropic", or "Co-authored-by".

## Atomic Standards

- **Single Intent:** One logical change per commit.
- **Integrity:** The commit must not break the build or leave the system in an unstable state.
- **Validation:** If the current diff contains unrelated changes, **STOP** and ask the user to split the changes.

## Execution Steps

### 1. Review

```bash
git diff --cached   # if already staged
git diff            # if not yet staged
```

### 2. Stage

```bash
git add <file1> <file2>   # specific files
git add .                  # only if all changes share one logical intent
```

Verify something is staged before proceeding:

```bash
if git diff --cached --quiet; then
    echo "❌ Nothing staged. Stage files first, then retry."
    exit 1
fi
```

### 3. Secret Scan (pre-commit)

```bash
# Primary: use project secret scanner if available
if [ -f "scripts/secret_scanner.py" ]; then
    python3 scripts/secret_scanner.py --staged
elif command -v git-secrets &> /dev/null; then
    git secrets --scan --cached
else
    # Fallback: grep-based scan on staged diff
    SECRETS_FOUND=$(git diff --cached | grep -iE \
        '(AKIA[0-9A-Z]{16}|sk_live_|ghp_[a-zA-Z0-9]{36}|xoxb-|-----BEGIN (RSA )?PRIVATE KEY-----|password\s*=\s*["\x27][^"\x27]+["\x27]|aws_secret_access_key\s*=)' \
        || true)
    if [ -n "$SECRETS_FOUND" ]; then
        echo "❌ POTENTIAL SECRETS DETECTED in staged changes:"
        echo "$SECRETS_FOUND"
        echo ""
        echo "STOP. Remove the secret, re-stage, and retry."
        exit 1
    fi
fi
# If secrets detected by any method: STOP. Do not commit. Remove the secret and re-stage.
```

### 4. Verify

```bash
git status
```

### 5. Commit

```bash
# Simple commit (no traceability)
git commit -m "<type>(<scope>): <description>"

# With traceability (when implementing a story)
git commit -m "<type>(<scope>): <description>

Implements: <STORY-KEY> AC-<N>
Refs: TDD <section reference>"
```

## Report

- **Message:** [The exact commit message used]
- **Status:** [Success/Failure] — [Short Hash]
- **Files:** [List of files included in this commit]
