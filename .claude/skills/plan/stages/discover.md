# DISCOVER

**Pattern:** Direct. Load `.claude/agents/requirements-analyst.md` for behavioral constraints before executing.
Interactive — needs user back-and-forth.

**On loop-back entry:** read loop_state.json → convergence already validated by `convergence_check.py` before dispatch.
Read `blocker_history` for context on what was previously tried and resolved — avoid re-asking resolved questions.

**Task tracking:** Use `TaskCreate`/`TaskUpdate`/`TaskList` to track each question as a task across turns. Create one
task per question when identified. Update status as: `pending` → `resolved` (answered) | `deferred` (user skipped, P2) |
`blocked` (needs external input). Check `TaskList` at start of each turn to know what remains.

**Steps:**

1. Read FEATURE_DRAFT.md → extract gaps + questions. On loop-back: also read loop_state findings.
2. For each question: `TaskCreate({title: "[PLAN] Q{N}: {question}", status: "pending", priority: "{P0|P1|P2}"})`
3. Classify gaps:
    - Resolvable from codebase → `[RESOLVED FROM CODE]`
    - Resolvable from Jira/Confluence → `[RESOLVED FROM DATA]`
    - Needs user → Q&A queue (apply AskUserQuestion format below)
3. After all questions resolved: `TaskUpdate` each to `resolved`. Write DISCOVERY_NOTES.md.

**DISCOVERY_NOTES.md format:**

Categories: Business Rules | UX | Edge Cases | Integration | Performance | Security

Per question:

```
### Q{N}: {question}
**Category:** {category}
**Answer:** {answer}
**Source:** user | codebase:file:line | jira:KEY | confluence:page
```

End with:

```
All Questions Resolved: YES
```

**Gate:** `All Questions Resolved: YES` at end of file → update state + auto-proceed to Draft.

```bash
python3 scripts/gate_transition.py {slug} planning Draft --artifact docs/features/{slug}/planning/DISCOVERY_NOTES.md
```
