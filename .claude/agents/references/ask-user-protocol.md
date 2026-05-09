---
description: AI-user alignment tool — decisions, clarifications, and open questions so every artifact is mature before proceeding.
argument-hint: "[category] [priority] [question]"
---

# AskUserQuestion

```
AskUserQuestion({
  questions: [{
    question: "[P{0|1|2}] {Specific question}. Why: {one-line downstream impact}.",
    header: "{Category}",
    options: [
      { label: "{Primary}", description: "⭐ Recommended — {reason}" },
      { label: "{Alt}",     description: "{outcome}" },
      { label: "Other",     description: "Type your own answer" },
      { label: "Discuss",   description: "Explore later — won't block" }
    ],
    multiSelect: {true|false}
  }]
})
```
**`header`** max 12 chars — `Biz Rules` · `Edge Cases` · `Integration` · `Performance` · `Security` · `Data Model` · `API` · `Architecture` · `Resilience` · `Migration` · `Observability`
**`multiSelect`** `false` = mutually exclusive (default) · `true` = multiple coexist
**Priority** `P0` blocks phase · `P1` before next phase · `P2` deferrable
**Options** `⭐ Recommended` only if grounded in PRD/TDD/codebase/prior decision — never Claude's own judgment · `Other` second-to-last · `Discuss` last · cap 4: 1 real → 3 · 2 real → 4 · 3 real → 4 (drop Discuss)
**Labels** no commas — multi-select splits on `, ` · keep labels short, unambiguous
**Question string** `[P{n}]` prefix + `Why:` suffix is full structure — do not embed more tokens

## Answers

| Selection | Value received                                                                                | Action |
|---|-----------------------------------------------------------------------------------------------|---|
| Real option | Selected `label`                                                                              | `✅ [{header}]: {summary}` — record, continue |
| Multi-select | Comma-joined labels                                                                           | Split on `, `, record each, continue |
| Other | User's typed text | Answer → record, continue · Question/clarification → resolve first, then record |
| Discuss | `"Discuss"`                                                                                   | → `[DISCUSS]` queue, continue — not a decision |
| P2 skipped | —                                                                                             | → `[OPEN QUESTION]` queue |

Dependency: note `→ Q{n+1} builds on this — {why}`

## Queues

**Blocking** `[OPEN QUESTION] [{Category}] [P{n}]: {question}` · `Impact: {what depends}`
**Non-blocking** `[DISCUSS] [{Category}]: {topic}` · `Context: {what triggered this}`

## Navigation

`progress` · `summary` · `skip` (→ P3 [OPEN QUESTION]) · `back` · `stop` (→ all remaining → [OPEN QUESTION])