---
name: init-feature
description: "Feature intake + route detection + tier classification. Run before /plan."
argument-hint: [feature-description or path/to/FEATURE_INPUT.md]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Init Feature

Resolve input → detect route → Q&A for gaps → classify tier (if not spike) → slug → scaffold dirs → gate.

**Template:** `FEATURE_INPUT_TEMPLATE.md`
**Prerequisites:** `config.yml` (`projects.active` set), `.claude/workflows/classification.yml`

## Step 1: Input Resolution

**Validate config first:**
```bash
python scripts/skill_setup.py --config-only
```
If `error` returned → HALT with message. Confirms `config.yml` exists, `projects.active` is set, active project `root` path is defined.

Then resolve input:
1. `FEATURE_INPUT.md` in HeadMaster root → validate, extract route + scope
2. Argument provided → seed, detect route, Q&A for gaps
3. No input → full Q&A

## Step 2: Route Detection

Detect from input before Q&A:

| Keywords | Route |
|----------|-------|
| spike, research, investigate, analyze, feasibility, explore, understand, map out | spike |
| fix, bug, patch, hotfix | hotfix |
| build, add, create, implement, feature, endpoint, service | feature |
| epic, initiative, multi-phase, program | epic |

Clear → confirm with user. Ambiguous → ask.

## Step 3: Q&A (missing fields only)

All user-facing questions → `AskUserQuestion` per `.claude/agents/references/ask-user-protocol.md`.

### Q1: Name + Goal
Ask if not in input.

### Q2: Repository + Module Discovery

**A. Read project root** from `config.yml → projects.{active}.root`.

**B. Registry check** — read `memory/projects/{active}/repo-registry.yml` if exists:
- Found → use registry as repo/module source. Present options via `AskUserQuestion`, `multiSelect: true`. Skip Steps C + D scan.
- Not found → warn: "Repo registry missing. Run `/setup-env` after init to cache for future features." Proceed to live scan below.

**Live scan** (registry absent): find subdirs (maxdepth 2) with build file markers (`pom.xml`, `build.gradle`, `settings.gradle`, `package.json`, `go.mod`, `requirements.txt`, `pyproject.toml`). Exclude `node_modules`, `target`, `build`, `dist`. Single → confirm. Multiple → `AskUserQuestion`, `multiSelect: true`.

**C. Module detection** (per selected repo): check for multi-module markers:
- Maven: `<modules>` in `pom.xml`
- Gradle: `include(...)` in `settings.gradle`
- npm: `workspaces` in `package.json`

If modules found → `AskUserQuestion` with list, `multiSelect: true`. If none → repo root is target.

**D. Tech stack** (per confirmed repo/module):
- Check `config.yml tools:` first — if registered, use directly, skip scan.
- Otherwise scan build files for language version, framework, build tool.
- `AskUserQuestion`: confirm detected stack or correct/add. Record `build_cmd`.

**Output per repo/module** → `FEATURE_INPUT.md` Repositories section:
```
### {repo-name}
- path: {relative to HeadMaster root}
- modules: [x, y]        # omit if single root
- tech: {lang+version, framework, build tool}
- build_cmd: {command}
```

### Q3: Effort + Design Complexity
Skip if spike.

### Q4: Research Questions
Spike only.

### Q5: External refs
Optional — Jira keys, Confluence IDs, local file paths.

### Q6: Constraints
Optional — NFRs, performance, compliance, compat.

### Q7: Ownership
Optional — defaults from `config.yml projects.{active}`.

---

Generate `FEATURE_INPUT.md` from answers → HeadMaster root. Placed in feature dir in Step 6.

## Step 4: Tier Classification

**If route == spike → set `complexity_tier: null`, `workflow: research`. Skip to Step 5. Do not classify.**

Otherwise: read `.claude/workflows/classification.yml`. Classify from effort + repos + design complexity → propose tier.

Confidence: HIGH (all agree) | MEDIUM (disagree by 1) | LOW (disagree by 2+). LOW → always ask user.

## Step 5: Slug + Duplicate Check + Pipeline Mode

**Slug:** lowercase, hyphens, max 40 chars.
- Autonomous mode → auto-generate from feature name, log to run-log.md, no confirmation.
- Interactive mode → propose slug, confirm with user via `AskUserQuestion`.

**Duplicate check** (before any scaffolding):
```bash
python -c "
from pathlib import Path
import json
p = Path('memory/features/{project}/{slug}/loop_state.json')
if p.exists():
    s = json.loads(p.read_text())
    phase = s.get('pipeline', {}).get('phase', '')
    stage = s.get('pipeline', {}).get('stage', '')
    print(f'EXISTS:{phase}/{stage}' if phase else 'INCOMPLETE')
"
```
- `EXISTS:{phase}/{stage}` → HALT: "Feature '{slug}' already active at {phase}/{stage}. Resume with /{phase} {slug} or choose a different slug."
- `INCOMPLETE` → `AskUserQuestion`: "Incomplete init found for '{slug}'. Overwrite or choose new slug?"
- No output → proceed.

**Pipeline mode:**
- spike → `plan-only` (always, no prompt)
- autonomous → `full` (always, log: "Pipeline: full (autonomous — auto-selected)")
- interactive → `AskUserQuestion`: full | skip-plan | skip-to-execute

## Step 6: Scaffold

**Dirs** — always create:
- `docs/features/{project}/{slug}/` → `input/`, `input/local-docs/`, `planning/`, `design/`, `breakdown/`
- `memory/features/{project}/{slug}/`

**skip-to-execute mode** — additional requirement before proceeding:
> Warn: "skip-to-execute requires TDD and JIRA_BREAKDOWN to exist before running /execute. Place them manually in `design/` and `breakdown/` after init completes."
> Next command in Step 7 → `/setup-env` (if registry missing) else guide user to place artifacts.

**loop_state.json:** write per `.claude/loop_state.json` schema. Required fields: `feature_slug`, `route`, `complexity_tier` (null if spike), `workflow`, `pipeline_mode`, `technical_owner`, `approver`.

**Ownership:** resolve in order — `projects.{active}` in config.yml → FEATURE_INPUT.md Ownership section → `"TBD"`.

**Place** FEATURE_INPUT.md → `input/`

**Local docs** (if user referenced files in Q5):
- Validate each path: must resolve within HeadMaster root or an absolute path the user explicitly provided. Reject `..` traversal outside project bounds.
- Size cap: skip files >500KB, warn user.
- Allowed extensions: `.md`, `.txt`, `.pdf`, `.yaml`, `.yml`, `.json`, `.adoc`. Warn and skip others.
- Copy valid files → `input/local-docs/`

**Post-write validation:**
```bash
python -c "
import sys
sys.path.insert(0, 'scripts')
from state_manager import validate_loop_state
from pathlib import Path
ok, err = validate_loop_state(Path('memory/features/{project}/{slug}/loop_state.json'))
if not ok: print('INVALID:' + err)
"
```
If `INVALID:` → HALT: "loop_state.json failed validation: {err}. Do not proceed."

```bash
python scripts/gate_transition.py {project} {slug} init complete \
  --artifact memory/features/{project}/{slug}/loop_state.json
```

## Step 7: Summary

```
Feature initialized: {slug}
Route: {route} | Tier: {tier or "N/A"} | Pipeline: {pipeline_mode} | Workflow: {workflow}
```

**Next command** — determined by pipeline_mode:

| pipeline_mode | Next |
|---------------|------|
| `full` | `/plan {slug}` |
| `skip-plan` | `/design {slug}` |
| `skip-to-execute` | Place `design/TDD*.md` + `breakdown/JIRA_BREAKDOWN*.md` manually, then `/execute {slug}` |
| `plan-only` | `/plan {slug}` |

Output next command only. Do not explain downstream behavior.