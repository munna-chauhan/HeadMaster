---
name: execute
description: "Drives JIRA_BREAKDOWN.md stories to completion. Per story: implement (inline) → scan (script) → review (subagent) → qa (subagent). System review (subagent) after all stories. Never writes code directly."
argument-hint: <feature-slug> [BREAKDOWN-FILE] [--story STORY-KEY]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Execute

Load `.claude/agents/release-agent.md`. Verify `config.yml` exists at repo root. If absent → HALT. Read values: `parallel`, `interactive`.

Mission: drive all stories to completion. Phase A (implement) + Phase B (scan) run inline. Verify phase (review + QA) spawns as a single combined subagent for l/m tiers (xs/s use inline or single subagent). Phase E (system review) spawns as isolated subagent. **Never write code.**

## Breakdown File Scoping (Optional)

**`/execute {slug} JIRA_BREAKDOWN_{NAME}.md`** — scope to one breakdown file only:
- Resolves TDD as `design/TDD_{NAME}.md` (or `TDD.md` if NAME absent)
- Validates that specific TDD is approved before proceeding
- Processes only stories from that breakdown file
- Phase E (system review) runs after all stories in that file complete
- Use case: multi-TDD features where each breakdown is executed independently

**`/execute {slug}`** — all breakdowns (merges all `JIRA_BREAKDOWN*.md` files).

## Single Story Mode (Optional)

If invoked with `--story STORY-KEY` flag:
- Load relevant JIRA_BREAKDOWN file and verify STORY-KEY exists
- Filter story list to process only that story (skip all others)
- All phases run normally (A → B → C → D)
- Phase E (system review) skipped (requires multiple stories for comparison)
- Use case: re-run failed story after manual fix, or implement single story for testing
- If story status already ✅ COMPLETE → warn and ask to confirm re-run

---

## Context Rules

- JIRA_BREAKDOWN*.md: extract story list (id, title, ACs, repo, SP) at init, cache as text — never hold full file
- Repo map: from PRD Repos section (l tier) or JIRA_BREAKDOWN story entries (xs/s/m) — grep heading, extract section only
- TDD: S3/S4 by heading grep per story's `design_section` — never full TDD
- Each phase reads only what it needs from disk

---

## Revision Check

Before dispatch, run:

```bash
python scripts/revision_manager.py check {project} {slug} execute
```

If `revision_open: true` → read `docs/features/{project}/{slug}/REVISION_NOTES.md` — Execute section of the open rev_id. Delta only: new stories (not in loop_state.json) + any `reopen: <KEY>` entries. COMPLETE stories not listed → skip. After all delta stories complete, append execution summary to Execute section, then close: `python scripts/revision_manager.py close {project} {slug} {rev_id}`.

---

## Stage Dispatch

Based on current execution state, load and execute the corresponding stage file:

| State                    | Action                                                          |
|--------------------------|-----------------------------------------------------------------|
| Not started / resuming   | Load and execute `.claude/skills/execute/stages/setup.md`       |
| Stories ready            | Load and execute `.claude/skills/execute/stages/story-loop.md`  |
| All stories done / escalation | Load and execute `.claude/skills/execute/stages/finalize.md` |

---

## Prerequisites

- `docs/features/{project}/{slug}/breakdown/JIRA_BREAKDOWN*.md` — human-approved
- `docs/features/{project}/{slug}/design/TDD*.md` OR `docs/features/{project}/{slug}/design/IMPLEMENTATION_BRIEF.md` — exists
- `artifacts["planning/PRD.md"].status = approved` in loop_state.json
