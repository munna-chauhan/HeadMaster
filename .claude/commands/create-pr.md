---
name: create-pr
description: Validate branch, check conflicts, build verify, and create PR with human merge gate.
argument-hint: <source-branch> <target-branch>
---

# /create-pr

Create a Pull Request for merging into protected branches. Human merge gate enforced.

## Arguments

- `$1` — source branch (e.g., `feature/my-feature`)
- `$2` — target branch (e.g., `main`)

Protected branches: `main`, `master`, `stable`, `release/*`. Only these require PRs.

## Steps

### 1. Idempotency check

```
gh pr list --head {source} --base {target} --state open
```

If PR already exists → report URL and stop. Do not create duplicate.

If `gh` CLI unavailable → check manually:
```
git log {target}..{source} --oneline
```
If empty (no commits ahead) → STOP, nothing to PR.

### 2. Pre-flight checks

```
git checkout {source}
git pull origin {source}
git checkout {target}
git pull origin {target}
```

Dry-run merge to detect conflicts:
```
git merge --no-commit --no-ff {source}
git merge --abort
git checkout {source}
```

If conflicts → HALT with conflicting file list.

### 3. Build verification

Detect build tool from codebase:
- `package.json` → `npm test -- --passWithNoTests`
- `pom.xml` → `mvn verify -DskipTests`
- `go.mod` → `go build ./...`
- `pyproject.toml` / `setup.py` → `pytest --collect-only`

Read override from config: `python scripts/config_utils.py get pipeline.build_command`

If detected → run on source branch. If build fails → HALT.
If not detected → log WARNING, continue.

### 4. Build PR title + body

**Title** — human-readable, not branch names:
1. If `loop_state.json` exists → use feature name from `feature_slug` + route: `feat: {feature name}` or `fix: {feature name}`
2. If commit messages share a prefix → extract: `feat(scope): summary`
3. Fallback → summarize diff intent in ≤70 chars, conventional commit format

Never use raw branch names as title.

**Body** — compose from available context:

| Source | Extract |
|--------|---------|
| Commits | `git log {target}..{source} --oneline` |
| loop_state.json | Feature summary, story count, tier |
| PRD/TDD links | `docs/features/{project}/{slug}/` (if exists) |
| JIRA_BREAKDOWN header | Epic key (if present) |
| SYSTEM_DESIGN_NOTES S12 | Rollback procedure (if present, else N/A) |
| `.github/PULL_REQUEST_TEMPLATE.md` | Merge template sections if exists |
| `CODEOWNERS` | Extract reviewers for changed paths |

### 5. Create PR

**Dry-run:** If `pipeline.dry_run: true` → log "DRY-RUN: would create PR {source} → {target}" with body preview. Stop.

```
gh pr create --base {target} --head {source} --title "{title}" --body-file {pr_body_path}
```

If `gh` CLI unavailable → output PR details for manual creation.

### 6. Human gate

```
⚠️  HUMAN MERGE BOUNDARY
PR created: {URL}
The physical merge to {target} requires human approval.
```

**STOP.** Do not merge. Human reviews and merges.

## Rollback

```
gh pr close {pr_number}
```

## Notes

- Auto-merges (story→feature, epic→feature) are direct git merges — no PR needed
