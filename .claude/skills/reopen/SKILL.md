---
name: reopen
description: "Reopen a completed pipeline stage for revision. Transitions artifact statuses, writes REVISION_NOTES.md, reports cascade chain. Downstream skills auto-detect revision mode via revision_manager.py."
argument-hint: <slug> [stage] [message]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Reopen

Reopen a completed pipeline stage so downstream skills run in **revision mode**.

## Invocation

```
/reopen {slug}                    → reopen latest completed stage
/reopen {slug} {stage}            → reopen specific stage
/reopen {slug} {stage} {message}  → same, with audit reason (recommended)
```

Valid stages: `planning` | `design` | `breakdown` | `execute`

---

## Setup

```bash
sh scripts/skill_setup.py {slug}
```

Use `project`, `slug` from output. If `error` is set → HALT.

If `{stage}` is omitted → infer from `pipeline.phase` in loop_state.json.

---

## Cascade Map

| Stage reopened | Re-run required in |
|----------------|--------------------|
| planning       | design → breakdown → execute |
| design         | breakdown → execute |
| breakdown      | execute |
| execute        | — (re-execute only) |

---

## Confirmation Gate (unconditional)

Show the user what will happen before proceeding:

```
Reopening: {slug} / {stage}
Artifacts → revision: {list}
Cascade: {list}
Reason: {message or "(none provided)"}

Confirm? [y/n]
```

Proceed only on explicit confirmation.

---

## Execution

```bash
sh scripts/revision_manager.py reopen {project} {slug} {stage} "{message}"
```

Script output JSON fields: `rev_id`, `cascade`, `artifacts_affected`, `log`, `next`, `error`.

If `error` is non-null → HALT and report.

---

## Responsibilities

1. Transitions artifact statuses for the reopened stage → `revision` (in loop_state.json)
2. Sets `pipeline.revision_open: true` + revision metadata (rev_id, stage, cascade, opened timestamp)
3. Resets `pipeline.phase` → reopened stage, `pipeline.stage` → `revision`
4. Writes/appends entry to `docs/features/{project}/{slug}/REVISION_NOTES.md` — scaffolds phase sections for reopened stage + cascade

Does NOT modify TDD, PRD, or breakdown files. Does NOT touch Jira.

---

## Output

```
Reopened: {slug} → {stage} [{rev_id}]
Artifacts revised: {N} ({list})
Cascade: {stage list or "none"}
REVISION_NOTES.md: {path}

Next steps:
  1. Fill the {stage} section in REVISION_NOTES.md — what changed and why
  2. Edit affected artifacts (PRD.md / TDD / breakdown) per your notes
  3. {next command from script output}
```

---

## Closing a Revision

Use `/reopen {slug} close {rev_id}` or call directly:

```bash
sh scripts/revision_manager.py close {project} {slug} {rev_id}
```

Close transitions:
1. Clears `pipeline.current_revision` from loop_state.json
2. Marks `revisions[].closed` with today's date
3. Updates REVISION_NOTES.md: `OPEN` → `CLOSED [{date}]`
4. Unblocks gate_transition — phase advance is permitted again

---

## Design Review Gate (when stage = design)

When reopening a `design` stage, before any TDD edits land:

1. Run `tdd-reviewer` on the current TDD artifacts in scope (read `pipeline.current_revision.artifacts_in_scope`)
2. Provide: REVISION_NOTES.md scope section + current TDD file content
3. `tdd-reviewer` must return PASS or CONDITIONAL before Engineer stage proceeds
4. Record verdict in loop_state.json: `pipeline.revision_review_verdict`

Skip this gate for `planning`, `breakdown`, `execute` stages.
