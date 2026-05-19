# Setup & Pre-flight

## Design Gate (HARD)

<HARD-GATE>

**Step A — Resolve breakdown scope:**
- If `BREAKDOWN-FILE` argument provided → use that file only. Extract `{NAME}` from filename.
- Otherwise → collect all `JIRA_BREAKDOWN*.md` from `breakdown/`. If none → HALT: "No breakdown found. Run `/breakdown {slug}` first."

**Step B — Validate each breakdown's backing artifact is approved:**

```bash
python -c "
from pathlib import Path
import sys, json

design_dir  = Path('docs/features/{project}/{slug}/design')
state_file  = Path('memory/features/{project}/{slug}/loop_state.json')
breakdown_files = {breakdown_file_list}  # resolved from Step A

state     = json.loads(state_file.read_text()) if state_file.exists() else {}
artifacts = state.get('artifacts', {})

for bf in breakdown_files:
    name = bf.stem.replace('JIRA_BREAKDOWN_', '').replace('JIRA_BREAKDOWN', '')
    # Resolve design artifact
    if not name or name == 'JIRA_BREAKDOWN':
        # Single-file feature: TDD.md or IMPLEMENTATION_BRIEF.md
        if (design_dir / 'IMPLEMENTATION_BRIEF.md').exists():
            print(f'OK:brief:{bf}')
            continue
        artifact_key = 'design/TDD.md'
        tdd = design_dir / 'TDD.md'
    else:
        artifact_key = f'design/TDD_{name}.md'
        tdd = design_dir / f'TDD_{name}.md'

    if not tdd.exists():
        print(f'MISSING:{tdd}')
        sys.exit(1)

    status = artifacts.get(artifact_key, {}).get('status')
    if status != 'approved':
        print(f'NOT_APPROVED:{tdd}')
        sys.exit(1)

    print(f'OK:tdd:{tdd}:{bf}')
"
```

- `MISSING:{tdd}` → HALT: "TDD not found for {bf}. Run `/design {slug}` first."
- `NOT_APPROVED:{tdd}` → HALT: "TDD not approved for {bf}. Run `/design {slug}` to complete review."
- All `OK:*` → proceed.

**Step C — PRD gate:**
```bash
sh scripts/gate_validator.py --project {project} --slug {slug} PRD_APPROVED
```
Fail → HALT: "PRD not approved. Run `/plan {slug}` first."

**Step D — phase guard:**
- `pipeline.phase = "init"` or `"planning"` → HALT: "Run /plan and /design first."

</HARD-GATE>

---

## Step 1: Initialize

**Validate:**

```
Any JIRA_BREAKDOWN*.md exists in breakdown/                              → proceed
TDD*.md OR IMPLEMENTATION_BRIEF.md exists                               → proceed
artifacts["planning/PRD.md"].status = approved (loop_state.json)        → proceed
Missing → HALT with specific message
```

**TDD coverage check (if TDD_MASTER.md exists):**

```bash
python -c "
import json, re, sys
from pathlib import Path
root      = Path('docs/features/{project}/{slug}')
master    = root / 'design/TDD_MASTER.md'
state_f   = Path('memory/features/{project}/{slug}/loop_state.json')
if not master.exists(): sys.exit(0)
tdd_names = re.findall(r'TDD_(\w+)\.md', master.read_text())
state     = json.loads(state_f.read_text()) if state_f.exists() else {}
released  = state.get('released_sections', {})
artifacts = state.get('artifacts', {})
for name in tdd_names:
    key    = f'design/TDD_{name}.md'
    status = artifacts.get(key, {}).get('status', 'unknown')
    if name not in released:
        print(f'{name}:{status}')
"
```

Classify each printed `{name}:{status}` line:

| Status | Meaning | Action |
|--------|---------|--------|
| `approved` | TDD approved, not yet broken down | ⚠️ needs breakdown — block or warn |
| `in_review` | Review in progress | ℹ️ informational only — do not block |
| `draft` | Written, not reviewed | ℹ️ informational only — do not block |
| `unknown` | Not tracked yet | ℹ️ informational only — do not block |

If any `approved` TDDs are not broken down → ask per `.claude/agents/references/ask-user-protocol.md`:

```
⚠️ Approved TDD sections not yet broken down: {names}
Options:
  A) Proceed with {N} stories from broken-down sections only
  B) Halt — run /breakdown {slug} {NAME} for each missing section first
```

If only `draft`/`in_review`/`unknown` TDDs are un-released → report as info, proceed without blocking.

If `TDD_MASTER.md` absent (single-TDD feature) → skip check.

---

**Story discovery — collect from ALL broken-down files:**

```
breakdown/JIRA_BREAKDOWN.md          → full breakdown (single TDD features)
breakdown/JIRA_BREAKDOWN_{NAME}.md   → partial breakdown (one released TDD section)
```

Merge into a single ordered story list. Each story carries its **source file** reference — status updates write back to the file that owns the story.

**Extract and cache (text only, not raw files):**

- Story list: id, title, ACs, dev_notes, repo, SP, blocked_by
- Repo map: name → path, build_cmd (from PRD Repos section, or from breakdown story entries)
- Config: `pipeline.max_loops`, `projects[active].jira_push`, `pipeline.parallel`
- `hm_root`: absolute path to HeadMaster repo — capture once via `git rev-parse --show-toplevel` (CWD is HeadMaster at setup time). Pass to every implement call so Phase A can call HeadMaster scripts with absolute paths even after `cd {repo_path}`.

**Register tasks:**

```
TaskCreate({title: "[EXEC] {LOCAL-ID}: {title}", status: "pending", ...})
```

**Update pipeline state:**

```bash
sh scripts/gate_transition.py {project} {slug} execute ready
```

---

## Step 2: Dependency Conflict Pre-flight

Skip if single repo. For multi-repo features:

**Path resolution — always use absolute paths:**
```python
from pathlib import Path
import shutil

hm_root   = Path(hm_root)          # absolute HeadMaster root captured in Step 1
repo_path = Path(repo_path)        # from repo_map; may be relative (e.g. ../PWR/foo)
abs_repo  = (hm_root / repo_path).resolve()
```
Never pass relative paths to `subprocess.run(cwd=...)`. Always `.resolve()` against `hm_root`.

| Stack | Dep file | Check command |
|-------|----------|---------------|
| Node  | `package.json` | Read + compare `dependencies` versions across repos |
| Java  | `pom.xml` | `subprocess.run(['mvn', 'dependency:tree', '-q', '-Dincludes=<pkg>'], cwd=abs_repo)` |
| Go    | `go.mod` | Read + compare `require` blocks |
| Python | `requirements.txt` / `pyproject.toml` | Read + compare version pins |

**Tool availability — check before running, never error on missing tool:**
```python
if not shutil.which('mvn'):
    print("WARNING: mvn not found — Java dep scan skipped")
    # continue, do not exit 1
```

Block on **major version conflicts** only → escalate with package + versions + repos.
Minor version differences → acceptable. Missing dep files → log WARNING, continue.

---

## Step 3: Git Pre-flight (per unique repo)

```bash
cd {repo_path}
# HALT if dirty — never silently stash
[ -z "$(git status --porcelain)" ] || HALT "Uncommitted changes in {repo_path}"
git fetch origin
MAIN=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')
git checkout $MAIN && git pull origin $MAIN
```

### Resume Integrity Check (IN PROGRESS stories only)

Per IN PROGRESS story → `git checkout story/{STORY-KEY}`:

| Check | Dirty/Fail action (AskUserQuestion) |
|-------|-------------------------------------|
| `git status --porcelain` not empty | Stash / reset --hard / escalate (mark FAILED, skip) |
| `{build_cmd}` fails | Reset soft HEAD~1 / escalate (mark FAILED, skip) |

Both clean → read `phases_completed` from `loop_state.json` for this story:

| `phases_completed` | Resume entry point |
|--------------------|--------------------|
| contains `"A"` | Skip Phase A — go directly to Phase B AC check |
| empty / absent | Start from Phase A |

This prevents re-running an already-committed Phase A after a mid-session crash.

---

## Step 4: Branch Setup (per unique repo)

Build branch hierarchy from JIRA_BREAKDOWN epic structure:

| Structure | Branches created | Story parent_branch |
|-----------|-----------------|---------------------|
| No epic (`epic_key = "None"`) | `feature/{slug}` | `feature/{slug}` |
| Single epic | `feature/{slug}` → `epic/{EPIC-KEY}` | `epic/{EPIC-KEY}` |
| Child epics | `feature/{slug}` → `epic/{EPIC-KEY}` → `child-epic/{CHILD-KEY}` per subsystem | `child-epic/{CHILD-KEY}` |

```bash
cd {repo_path}

# 1. Feature branch (always)
git show-ref --quiet refs/remotes/origin/feature/{slug} \
  && (git checkout feature/{slug} && git pull) \
  || /create-branch {MAIN} feature {slug}

# 2. Epic branch (if epic_key exists and != "None")
# /create-branch feature/{slug} epic {EPIC-KEY}

# 3. Child-epic branches (if child epics exist)
# /create-branch epic/{EPIC-KEY} child-epic {CHILD-KEY}
```

Cache `parent_branch` per story — resolved from its Epic field in JIRA_BREAKDOWN:

| Story's Epic field | parent_branch |
|--------------------|---------------|
| Child-epic key | `child-epic/{CHILD-KEY}` |
| Epic key (no children) | `epic/{EPIC-KEY}` |
| None / absent | `feature/{slug}` |

Pass `parent_branch` to implement context per story.
