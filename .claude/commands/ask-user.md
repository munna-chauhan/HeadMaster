# AskUserQuestion Format

Load: `ToolSearch → query: "select:AskUserQuestion"`

## Decision Rule

Ask only if:

- Two valid options exist with real trade-offs + no clear winner from code/context/Jira/Confluence
- A class/file is missing that materially affects requirements (flag as risk question)
- A business rule has two contradictory sources (flag as conflict question)

Never ask:

- Anything resolvable from codebase, Jira, Confluence, or config
- Generic questions ("how should we handle errors?", "what format?")
- Questions where one option is clearly better given context

Autonomous mode (`interactive: false`): auto-select best option, log rationale — EXCEPT when confused.
Confusion = ambiguity, contradiction, missing critical input, or destructive action.
If confused: ask using this same format. Tag header `[CLARIFICATION]`. Resume auto-mode after answer.

## Question Format

One question at a time. Acknowledge each answer before next question.

```
AskUserQuestion({
  "questions": [{
    "header": "Label (12 chars)",
    "question": "Q{n} [{category}] [{priority}]: {Specific question with full context.}\n\nWhy this matters: {impact on downstream phases if wrong}\n\nFound: {what code/Jira/Confluence shows — cite source}",
    "multiSelect": false,
    "options": [
      {
        "label": "Option A (Recommended)",
        "description": "✅ {pros} / ⚠️ {cons}"
      },
      {
        "label": "Option B",
        "description": "✅ {pros} / ⚠️ {cons}"
      },
      {
        "label": "Flag as risk — decide later",
        "description": "Document as [OPEN QUESTION] or risk. Unblocks progress."
      }
    ]
  }]
})
```

**Priority tags:**

- `P0` — blocks current phase gate. Must resolve before proceeding.
- `P1` — important. Resolve before next phase.
- `P2` — nice-to-know. Can defer to implementation.

**Category tags:**
`Business Rules` · `Edge Cases` · `Integration` · `Performance` · `Security` · `Data Model` · `API Contract` · `Architecture` · `Resilience` · `Migration` · `Observability`

## After Each Answer

```
✅ Q{n}: {summary of answer chosen}
{If follow-up needed}: Q{n+1} builds on this — {why}
```

Adaptive follow-ups: use previous answers to shape next question.

## User Navigation Commands

Respond to these at any point during Q&A:

- `progress` → show Q{done}/{total}, list resolved answers so far
- `summary` → show all answers recorded so far
- `skip` → mark current question P2, move to next
- `back` → revisit previous question, update answer
- `stop` → halt Q&A, record remaining as `[OPEN QUESTION]` in output

## Multiselect (when applicable)

Use `"multiSelect": true` only when multiple options can genuinely coexist (e.g. "which edge cases apply?"). Never use
for mutually exclusive decisions.
