# Breakdown Stage: Merge Gate

Post-execution PR checklist. Invoked after all stories complete.

---

## Prerequisites

- All stories in JIRA_BREAKDOWN.md = ✅ COMPLETE
- `docs/features/{slug}/retrospective/system-review.md` exists and clean
- No 🔄 IN PROGRESS or ⚪ DEFERRED stories blocking merge

---

## Checklist

```markdown
## Merge Gate: {slug}

- [ ] All stories COMPLETE in JIRA_BREAKDOWN.md
- [ ] System review passed (0 critical/high findings)
- [ ] No BLOCKED or FAILED stories
- [ ] PR created from feature/{slug} to target branch
- [ ] PR body includes system-review summary
- [ ] Human reviewer assigned
- [ ] Rollback procedure documented (from SYSTEM_DESIGN_NOTES S12 or IMPLEMENTATION_BRIEF, if applicable)
```

---

## PR Body Template

```markdown
## {Feature Name}

**PRD:** docs/features/{slug}/planning/PRD.md
**TDD:** docs/features/{slug}/design/TDD*.md
**Stories:** {N} stories, {N} SP

### Changes
{Summary organized by repo if multi-repo}

### System Review
{Key findings from system-review report — PASS or findings list}

### Testing
{Coverage summary from QA integration reports}

### Rollback
{From SYSTEM_DESIGN_NOTES.md S12 or N/A for lite tier}
```

---

## Gate

Human merges PR. Never auto-merge.

---

## Completion

```
Merge Gate: {slug}

Checklist verified. PR ready.
Next: Human review + merge to {target-branch}
```
