# Breakdown Stage: Decompose

TDD → Jira stories + epic. Steps 1-8.

---

## Argument Parsing

```
/breakdown {slug}           → full mode   (single TDD.md or IMPLEMENTATION_BRIEF.md)
/breakdown {slug} TDD_API   → partial mode (TDD_API.md only → JIRA_BREAKDOWN_TDD_API.md)
```

| Mode | Requires | Output | Notes |
|------|----------|--------|-------|
| Partial | `TDD_{NAME}.md` + `TDD_MASTER.md` | `JIRA_BREAKDOWN_{NAME}.md` | Update `TDD_MASTER.md` after |
| Full | Single `TDD.md` or `IMPLEMENTATION_BRIEF.md` | `JIRA_BREAKDOWN.md` | HALT if `TDD_MASTER.md` present without argument |

---

## Step 1: Read Inputs (single pass)

TDD approval check (partial mode only):

```bash
python -c "
import json, sys
from pathlib import Path
state_file = Path('memory/features/{project}/{slug}/loop_state.json')
if not state_file.exists(): sys.exit(0)
state = json.loads(state_file.read_text())
key = 'design/TDD_{NAME}.md'
status = state.get('artifacts', {}).get(key, {}).get('status', 'unknown')
if status != 'approved':
    print(f'BLOCKED: {key} status={status} (required: approved)')
    sys.exit(1)
"
```

HALT if exit code 1 — TDD must be `approved`. Run `/design {slug}` to complete review.

For full mode (single `TDD.md`): verify `artifacts["design/TDD.md"].status = approved`. HALT if not.

Allowed inputs — ONLY these files:

| Mode | Files |
|------|-------|
| Partial | `TDD_MASTER.md` (index/context only) + specified `TDD_{NAME}.md` |
| Full | `TDD.md` or `IMPLEMENTATION_BRIEF.md` + `PRD.md` |

**Size guard:** If TDD file exceeds 500 lines → extract by section heading. Read S3 (Interfaces), S4 (Data), S5 (Implementation), S6 (Stories) only. Skip S1/S2 (context already in PRD) and S7+ (test strategy is post-breakdown concern).

---

## Step 2: Intelligence Pass

Classify slices, estimate SP, detect dependencies per `.claude/agents/release-agent.md` TPM persona. Agent owns classification rules, SP estimation, and story quality.

**Orchestration annotations (skill-level):**

Parallel groups: stories with no shared deps + different repos → mark `PARALLEL_GROUP_{N}`. Informational unless `pipeline.parallel: true`.

Relationships: `Blocks`/`Blocked By` (sequential dep) | `Related` (shared context) | `Duplicate` → merge.

**AC quality gate (per story, before writing JIRA_BREAKDOWN.md):**

Every story with user input or external integration must include ≥1 unhappy-path AC (error handling, validation failure, timeout, auth rejection). Flag stories missing error/edge ACs → add before proceeding to Step 5.

---

## Step 3: Epic Decision

`< 3 stories → no epic | >= 3 stories → epic needed`

Epic lookup (read-only, no Jira MCP fetch):

| Priority | Source | Extract |
|----------|--------|---------|
| 1 | `FEATURE_DRAFT.md` frontmatter | `jira.epic_key` |
| 2 | `FEATURE_INPUT.md` § 3 | parent epic key |
| 3 | `config.yml` → `capabilities.epic_strategy` | see table below |

| strategy | action |
|----------|--------|
| `auto_create` | epic_key = "EPIC-NEW (pending)" |
| `link_existing` / unset+interactive | AskUserQuestion per ask-user-protocol |
| `none` | epic_key = "None" |
| unset + autonomous | epic_key = "EPIC-NEW (pending)" |

≥2 independent subsystems each with ≥3 stories → propose child epics, ask per protocol.

---

## Step 4: Existing Ticket Reconciliation

Keyword-match story titles against Jira keys found in Step 3:

| Match | Action |
|-------|--------|
| Match + Done/Closed/Resolved | ✅ COMPLETE — skip (see Revision Mode below) |
| Match + open | ⬆️ EXISTING — diff title/desc/ACs, surface for human review. Do NOT auto-update. |
| No match | ⏳ NEW |

**Revision Mode** (when `python scripts/revision_manager.py check {project} {slug} breakdown` confirms `revision_open`):

| REVISION_NOTES directive | Action |
|--------------------------|--------|
| `add:` | New story |
| `suspend:` | Mark DEFERRED |
| `reopen:` | Replacement story (link "Supersedes: KEY") |
| (unlisted COMPLETE) | Still skip |

Append summary to REVISION_NOTES.md after writing.

---

## Step 5: Write JIRA_BREAKDOWN.md

### Tier Re-Assessment (mandatory first)

Count stories (exclude COMPLETE), sum SP, scan dev_notes for breaking signals (`breaking change`, `database migration`, `new service`, `breaking api`).

Load thresholds from `.claude/workflows/{original_tier}.yml` → `escalation_thresholds`.

If breached → AskUserQuestion: "Tier mismatch: {original_tier} → {story_count} stories, {total_sp} SP, {N} breaking changes."
- ESCALATE → update `tier` in loop_state.json
- KEEP → require justification, log via run_logger.py
- ABORT → write `tier_mismatch: true`, HALT

### Write File

Path: Full → `breakdown/JIRA_BREAKDOWN.md` | Partial → `breakdown/JIRA_BREAKDOWN_{NAME}.md`

Load template from: `.claude/skills/breakdown/references/jira-breakdown-template.md`

Write header, story overview table, dependency graph, then per-story content following template format.

---

## Step 5a: Write design_section per story

After writing JIRA_BREAKDOWN, update `loop_state.json stories.{KEY}.design_section` for every story:

| Mode | design_section value |
|------|---------------------|
| `IMPLEMENTATION_BRIEF.md` | `null` |
| Single `TDD.md` | `"TDD"` |
| Partial `TDD_{NAME}.md` | `"{NAME}"` |

```bash
python -c "
import json
from pathlib import Path
state_file = Path('memory/features/{project}/{slug}/loop_state.json')
state = json.loads(state_file.read_text())
state.setdefault('stories', {})
for key in {story_key_list}:
    state['stories'].setdefault(key, {})['design_section'] = {design_section_value}
state_file.write_text(json.dumps(state, indent=2))
"
```

Mandatory — downstream agents resolve TDD file from this field.

---

## Step 5b: Record Release (partial mode only)

1. Update TDD_MASTER.md — find `TDD_{NAME}.md` row in delivery table. Append to `## Released Sections`:
```markdown
| TDD_{NAME}.md | {ISO-date} | JIRA_BREAKDOWN_{NAME}.md | {N} stories, {N} SP |
```
If section doesn't exist, create it. Never modify existing rows.

2. Write to loop_state.json:
```bash
python scripts/gate_transition.py {project} {slug} released-section \
  "{NAME}" "breakdown/JIRA_BREAKDOWN_{NAME}.md" "{N}" "{N_SP}"
```

Both updates mandatory. HALT if either fails.

---

## Step 6: Session Resilience

```
For each story (status != COMPLETE):
TaskCreate({ title: "[EXEC] {LOCAL-ID}: {title}", status: "pending",
  details: "Repo: {repo} | SP: {N} | Priority: {P} | Blocked By: {deps} | Parallel: {group}" })
```

---

## Step 7: Human Gate

Default: Unconditional. Cannot bypass via autonomous mode alone.

Autonomous bypass (local only): `autonomous: true` AND `gates.breakdown.auto_approve: true` AND `jira_push: false` → log and skip to Completion.

Ask per `.claude/agents/references/ask-user-protocol.md` — topic: "Approve breakdown: {N} stories | {N} SP | critical path {N} SP | {N} parallel groups."

| Option | Action |
|--------|--------|
| Approve + push | Creates NEW stories/epic, flags EXISTING for update |
| Approve local | Keep LOCAL IDs, execute from file |
| Revise first | Stop, edit JIRA_BREAKDOWN.md, re-run `/breakdown {slug}` |
| Skip to execution | Go to `/execute` using TDD slices directly |

---

## Step 8: Jira Push (Conditional)

Only if human selects "push to Jira" AND `jira_push: true`. If `pipeline.dry_run: true` → skip writes, Push Status → `DRY-RUN MODE`.

Route all Jira writes through `/jira-ops` — never call MCP tools directly.

Operations (in order):
1. Create epic (if EPIC-NEW) → store real key
2. Per ⏳ NEW → `jira_ops.py create-story`
3. Per ⬆️ EXISTING → update title + desc + ACs only. Never touch status/assignee/sprint.
4. Create `Blocks`/`Blocked By`/`Related` links
5. Post epic comment with breakdown summary
6. Update JIRA_BREAKDOWN.md: replace LOCAL IDs with real keys. Push Status → `PUSHED TO JIRA`.
7. Update TaskCreate details with real Jira keys.

If Jira unavailable after 3 retries (5s/10s/20s) → write `JIRA_MANUAL_LOG.md`, Push Status → `PUSH FAILED`.

---

## Completion

```bash
python scripts/gate_transition.py {project} {slug} artifact \
  "breakdown/JIRA_BREAKDOWN{_NAME}.md" "{push_status}"
python scripts/gate_transition.py {project} {slug} breakdown approved
```

`{push_status}` = `pushed` | `local` | `draft`

Report: story count, SP total, critical path SP, epic key, push status. Suggest `/execute {slug}`.
