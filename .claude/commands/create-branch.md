---
name: create-branch
type: command
description: Syncs with a base branch, stashes local changes, and creates a new standardized branch with explicit type prefix.
argument-hint: <base-branch> <type> <name>
---

# Create Git Branch

Switch to a base branch, update it, and create a new branch with a standardized name.

## Arguments

- **`$1`** — Base branch to branch from (e.g., `main`, `feature/my-feature`, `epic/PROJ-100`)
- **`$2`** — Branch type prefix: `story`, `feature`, `epic`, `child-epic`, `fix`
- **`$3`** — Branch name or key (e.g., `PROJ-123`, `my-feature`, `add-login`)

## Usage

```
/create-branch main feature my-feature
/create-branch feature/my-feature story PROJ-123
/create-branch epic/PROJ-100 story PROJ-456
/create-branch main fix critical-bug
```

## Step 1: Validate Inputs

```bash
# Validate type prefix
VALID_TYPES="story feature epic child-epic fix"
if ! echo "$VALID_TYPES" | grep -qw "$2"; then
    echo "❌ Invalid branch type: $2"
    echo "   Allowed: $VALID_TYPES"
    exit 1
fi

# Validate base branch exists
if ! git show-ref --verify --quiet "refs/heads/$1" && \
   ! git show-ref --verify --quiet "refs/remotes/origin/$1"; then
    echo "❌ Base branch does not exist: $1"
    exit 1
fi
```

## Step 2: Save Pending Work

```bash
if [ -n "$(git status --porcelain)" ]; then
    echo "Stashing local changes..."
    git stash save "Auto-stash before branching from $1"
fi
```

## Step 3: Prepare the Base

```bash
git checkout "$1"
git pull origin "$1"
```

If the pull fails (merge conflicts), **STOP** and alert the user.

## Step 4: Generate and Create New Branch

```bash
# Slugify name: lowercase, replace non-alphanumeric with hyphens, collapse duplicates
NEW_SLUG=$(echo "$3" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')

FINAL_NAME="${2}/${NEW_SLUG}"

# Check for existence, append version suffix if needed
if git show-ref --verify --quiet "refs/heads/${FINAL_NAME}"; then
    VERSION=2
    while git show-ref --verify --quiet "refs/heads/${FINAL_NAME}-v${VERSION}"; do
        VERSION=$((VERSION + 1))
    done
    FINAL_NAME="${FINAL_NAME}-v${VERSION}"
fi

git checkout -b "$FINAL_NAME"
```

## Step 5: Push (if remote tracking needed)

```bash
# Push and set upstream for pipeline branches (feature, epic, child-epic)
case "$2" in
    feature|epic|child-epic)
        git push -u origin "$FINAL_NAME"
        ;;
esac
# story and fix branches: push deferred until first commit
```

## Step 6: Cleanup

```bash
git stash list   # Remind the user their stashed work is safe
```

## Report

- **Branch Created:** [full branch name]
- **Based On:** [base branch + commit hash]
- **Pushed:** [Yes/No]
- **Stash:** [Yes/No — stash reference if applicable]
