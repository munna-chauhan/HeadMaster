---
name: create-branch
description: Create a standardized branch from a base branch with type prefix, stash safety, and naming validation.
argument-hint: <base-branch> <type> <name>
---

# /create-branch

Create a new branch with standardized naming from a base branch.

## Arguments

- `$1` — base branch (e.g., `main`, `feature/my-feature`, `epic/PROJ-100`)
- `$2` — branch type: `story`, `feature`, `epic`, `child-epic`, `fix`
- `$3` — branch name or key (e.g., `PROJ-123`, `my-feature`)

## Steps

### 1. Validate inputs

Verify type is one of: `story`, `feature`, `epic`, `child-epic`, `fix`. If not → STOP.

Verify base branch exists:
```
git show-ref --verify refs/heads/{base}
git show-ref --verify refs/remotes/origin/{base}
```
If neither exists → STOP.

### 2. Stash pending work

```
git status --porcelain
```
If dirty → `git stash push -m "Auto-stash before branching from {base}"`

### 3. Prepare base

```
git checkout {base}
git pull origin {base}
```
If pull fails (conflicts) → STOP, alert user.

### 4. Generate branch name

Slugify: lowercase, replace non-alphanumeric with hyphens, collapse duplicates, trim edges.

```python
python -c "
import re, sys
name = sys.argv[1].lower()
name = re.sub(r'[^a-z0-9]', '-', name)
name = re.sub(r'-+', '-', name).strip('-')
print(name)
" "{name}"
```

Final name: `{type}/{slug}`

If branch already exists → append `-v2`, `-v3`, etc.

### 5. Create branch

```
git checkout -b {type}/{slug}
```

### 6. Push (conditional)

For `feature`, `epic`, `child-epic` → push and set upstream:
```
git push -u origin {type}/{slug}
```

For `story`, `fix` → defer push until first commit.

**Dry-run:** If `pipeline.dry_run: true` → skip push, log "DRY-RUN: would push {branch}".

### 7. Report

```
Branch Created: {full name}
Based On: {base} @ {short hash}
Pushed: {Yes|No|DRY-RUN}
Stash: {Yes (ref)|No}
```

## Rollback

```
git checkout {base}
git branch -d {type}/{slug}
git push origin --delete {type}/{slug}   # if pushed
git stash pop                             # if stashed
```
