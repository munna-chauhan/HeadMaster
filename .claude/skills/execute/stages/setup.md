# Setup & Pre-flight

## Step 1: Initialize

**Validate:**

```
JIRA_BREAKDOWN.md exists + human-approved  → proceed
TDD*.md OR IMPLEMENTATION_BRIEF.md exists  → proceed
PRD.md with PRD Status: APPROVED           → proceed
Missing → HALT with specific message
```

**Extract and cache (text only, not raw files):**

- Story list: id, title, ACs, dev_notes, repo, SP, status, blocked_by
- Repo map: name → path, build_cmd (from PRD Repos section, or from JIRA_BREAKDOWN.md story entries)
- Config: max_loops, jira_push, parallel

**Register tasks:**

```
TaskCreate({title: "[EXEC] {LOCAL-ID}: {title}", status: "pending", ...})
```

**Update pipeline state:**

```bash
python3 scripts/gate_transition.py {slug} execute ready --artifact docs/features/{slug}/breakdown/JIRA_BREAKDOWN.md
```

---

## Step 2: Pre-flight (per unique repo)

```bash
cd {repo_path}
git status --porcelain | grep -q . && git stash save "execute-preflight-{slug}"
git fetch origin
MAIN=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')
git checkout $MAIN && git pull origin $MAIN
```

### Resume Integrity Check (runs ONLY when resuming — stories already IN PROGRESS in JIRA_BREAKDOWN.md)

Per IN PROGRESS story:

1. `git checkout story/{STORY-KEY}`
2. Check `git status --porcelain` — if dirty:
   - AskUserQuestion: "story/{STORY-KEY} has uncommitted changes. Stash, reset --hard, or escalate?"
   - Stash → `git stash save "crash-recovery-{STORY-KEY}"`
   - Reset → `git reset --hard HEAD`
   - Escalate → mark FAILED, skip story
3. Run `{build_cmd}` — if fails:
   - AskUserQuestion: "story/{STORY-KEY} last commit doesn't build. Reset soft HEAD~1, or escalate?"
   - Reset → `git reset --soft HEAD~1` then re-attempt build
   - Escalate → mark FAILED, skip story
4. If both clean → proceed normally with this story

---

## Step 3: Branch Setup (per unique repo)

```bash
git show-ref --quiet refs/remotes/origin/feature/{slug} \
  && (git checkout feature/{slug} && git pull) \
  || /create-branch {MAIN} feature {slug}
```
