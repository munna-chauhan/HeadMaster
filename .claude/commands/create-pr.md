---
name: create-pr
type: command
description: Validate branch hierarchy, check for conflicts, and create a PR with human merge gate for protected branches.
argument-hint: <source-branch> <target-branch>
---

# Command: Create PR

## Purpose

Validate branch hierarchy, check for conflicts, and create a Pull Request for merging into protected branches (
main/master/stable/release/*). Used by /execute (Step 7) and available for standalone use.

## Usage

```
/create-pr <source-branch> <target-branch>
```

## Step 1: Resolve Config

```bash
CONFIG="config.yml"
```

## Step 2: Validate Branch Hierarchy

Verify source branch follows naming convention and target is a protected branch.
Protected branches: main, master, stable, release/*. Only these require PRs.

## Step 3: Pre-flight Checks

Run from within the target repo directory.

```bash
git checkout $1 && git pull origin $1
git checkout $2 && git pull origin $2

# Dry-run merge: merge source INTO target to detect conflicts
git merge --no-commit --no-ff $1
git merge --abort
git checkout $1
```

If conflicts detected → **HALT** with conflicting file list.

## Step 4: Create PR

```bash
gh pr create \
  --base "$2" \
  --head "$1" \
  --title "$1: merge to $2" \
  --body "## Summary
{1-3 bullets of what this merges}

## Checklist
- [x] Build green
- [x] Code review passed
- [x] QA approved (if applicable)"
```

If `gh` CLI unavailable, output PR details for manual creation.

## Step 5: Human Gate

```
⚠️  HUMAN MERGE BOUNDARY
PR created: {URL}
The physical merge to $2 requires human approval.
```

**STOP.** Do not merge. Human reviews and merges.

## Notes

- Only for protected branches (main/master/stable/release/*).
- Auto-merges (story→epic/feature, epic→feature) are direct git merges handled by /execution — no PR needed.
