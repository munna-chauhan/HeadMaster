---
name: archive-feature
description: Archive completed features to clean up project directory. Preserves all data for historical reference.
argument-hint: <project> <feature-slug>
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Archive Feature

Move completed features to archive directory. Preserves docs, memory, cost history.

## Usage

```
/archive-feature <project> <feature-slug>
```

## Step 1: Validate + Archive

```
python .claude/skills/archive-feature/scripts/archive_feature.py archive {project} {slug}
```

Script checks `loop_state.json` status = "completed". If not completed → prompts for confirmation or `--force`.

Moves:
- `docs/features/{project}/{slug}/` → `docs/features/{project}/archive/{slug}/`
- `memory/features/{project}/{slug}/` → `memory/features/{project}/archive/{slug}/`

Creates `archive_metadata.json` with timestamp.

## Step 2: Confirm

```
✅ Feature '{slug}' archived successfully
```

## Restore

```
python .claude/skills/archive-feature/scripts/archive_feature.py restore {project} {slug}
```

Moves back to active locations.

## List Archives

```
python .claude/skills/archive-feature/scripts/archive_feature.py list {project}
```

Shows all archived features with timestamps.

## Integration

- Run at DONE/CANCELLED to keep `memory/features/` clean
- Archived features excluded from `state_manager.py --status`
