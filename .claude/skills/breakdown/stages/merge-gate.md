# Breakdown Stage: Merge Gate

Post-execution PR checklist. Invoked after all stories complete.

---

## Prerequisites

- All stories in `JIRA_BREAKDOWN*.md` = ✅ COMPLETE (verify against `loop_state.json` stories — all status = COMPLETE)
- `docs/features/{project}/{slug}/retrospective/system-review.md` exists and clean
- No 🔄 IN PROGRESS or ⚪ DEFERRED stories blocking merge

---

## Pre-approval checks

**Step 1: Review decision log**

```bash
grep -i "LOW\|tier_override\|STORY_FAIL\|STORY_DEFER" \
  memory/features/{project}/{slug}/run-log.md | tail -20
```

If any LOW-confidence or override entries found → display them inline before proceeding. Do not require human to open the file. If run-log.md is empty or absent → skip.

**Step 2: Checklist**

```markdown
## Merge Gate: {slug}

- [ ] All stories COMPLETE in JIRA_BREAKDOWN.md
- [ ] System review passed (0 critical/high findings)
- [ ] No BLOCKED or FAILED stories
- [ ] Assumptions reviewed (if any — see above)
- [ ] PR created from feature/{slug} to target branch (skipped if dry-run mode)
- [ ] PR body includes system-review summary
- [ ] Human reviewer assigned
- [ ] Rollback procedure documented (SYSTEM_DESIGN_NOTES.md if present, IMPLEMENTATION_BRIEF.md for xs tier, or N/A)
```

**Dry-run mode:** If `pipeline.dry_run: true`, skip PR creation (`gh pr create`), log "DRY-RUN: Skipped PR creation" to stderr, report checklist results only.

---

## PR Body Template

```markdown
## {Feature Name}

**PRD:** docs/features/{project}/{slug}/planning/PRD.md
**TDD:** docs/features/{project}/{slug}/design/TDD*.md
**Stories:** {N} stories, {N} SP

### Changes
{Summary organized by repo if multi-repo}

### System Review
{Key findings from system-review report — PASS or findings list}

### Testing
{Coverage summary from QA integration reports}

### Rollback
{From SYSTEM_DESIGN_NOTES.md if present, IMPLEMENTATION_BRIEF.md for xs tier, or N/A}
```

---

## Gate

**PERMANENT GATE: Cannot bypass via any config or mode.**

Always requires human approval regardless of `autonomous: true`. PR creation affects team workflow — final sanity check before team handoff.

Human merges PR. Never auto-merge.

---

## Completion

```
Merge Gate: {slug}

Checklist verified. PR ready.
Next: Human review + merge to {target-branch}
```
