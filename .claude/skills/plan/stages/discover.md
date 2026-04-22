# DISCOVER

**Pattern:** Direct. Load `.claude/agents/requirements-analyst.md` + `.claude/commands/ask-user.md` before executing.
All question quality and format rules come from `ask-user.md` — do not duplicate here.

**On loop-back:** read `loop_state.json` → `blocker_history` for previously resolved questions. Don't re-ask.

**Task tracking:** `TaskCreate`/`TaskUpdate`/`TaskList` per question across turns.
Status flow: `pending` → `resolved` | `deferred` (skipped/below threshold) | `blocked` (needs external input).

**Steps:**

1. Read FEATURE_DRAFT.md → extract gaps + questions. On loop-back: also read loop_state findings.
2. Per question: `TaskCreate({title: "[PLAN] Q{N}: {question}", status: "pending", priority: "{P0|P1|P2}"})`
3. Classify gaps:
    - Resolvable from codebase → `[RESOLVED FROM CODE]`
    - Resolvable from Jira/Confluence → `[RESOLVED FROM DATA]`
    - Meets ask-user.md threshold → ask user
    - Below threshold → `[ASSUMPTION]` with justification, `TaskUpdate` to `deferred`
4. After all questions resolved or deferred: write DISCOVERY_NOTES.md.

**DISCOVERY_NOTES.md format:**

Categories: Business Rules | UX | Edge Cases | Integration | Performance | Security

```
### Q{N}: {question}
**Category:** {category}
**Answer:** {answer}
**Source:** user | codebase:file:line | jira:KEY | confluence:page
```

End with: `All Questions Resolved: YES`

**Gate:** gate string present → auto-proceed to Draft.

```bash
python3 scripts/gate_transition.py {slug} planning Draft --artifact docs/features/{slug}/planning/DISCOVERY_NOTES.md
```
