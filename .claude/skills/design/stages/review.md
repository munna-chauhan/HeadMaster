# REVIEW

**Pattern:** Direct (inline). New session required — Engineer must have stopped in prior session.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

**Session boundary:** This stage only runs when `design_stages.engineer = complete` in loop_state.json. If called in the same session as Engineer, HALT: "Start a new session: /design {slug} to review."

Mark in_progress on entry:
```bash
python scripts/gate_transition.py {project} {slug} design-stage review in_progress
```

---

## When to Run

**1. Check tier workflow** (`.claude/workflows/{tier}.yml` → `stages.tdd_review.status`):

| Status | Action |
|--------|--------|
| `skip` (xs) | Skip review → mark TDD APPROVED via gate_transition → breakdown |
| `optional` | Proceed to mode check |
| `required` | Proceed to mode check |

**2. Check `gates.design.review.mode`** in config.yml:

| Mode | Behavior |
|------|----------|
| `human_in_loop` | TDD alignment session (see below) → run tdd-reviewer → present findings → final approval gate |
| `auto` | Run tdd-reviewer → APPROVED/CONDITIONAL → auto-approve; REJECTED + convergence failure → escalate to human. Log all to run-log.md |
| `skip` | Skip tdd-reviewer → mark TDD APPROVED immediately. Log: "TDD review skipped per gates.design.review.mode=skip" |

---

## TDD Alignment Session (human_in_loop only)

Run before spawning tdd-reviewer. Read TDD section headings + first 3 lines per section (offset/limit only — do not load full TDD). Ask these four questions, one at a time via AskUserQuestion:

| # | Header | Question | What to extract from TDD |
|---|---|---|---|
| 1 | `Delivery` | "[P1] Vertical slices: {slice list}. Do these match your deployment preference — each slice independently deployable?" | Section: Vertical Delivery Slices |
| 2 | `Interfaces` | "[P1] Key interfaces: {interface list}. Do these align with your codebase patterns?" | Section: Data Models & Contracts |
| 3 | `ADRs` | "[P1] Decisions made: {ADR titles}. Any you'd challenge before we run the reviewer?" | Section: ADRs |
| 4 | `Testing` | "[P1] Testing strategy: {strategy summary}. Does this match your team's testing practices?" | Section: Testing Strategy |

Apply corrections inline to TDD after each answer. Then proceed to spawn tdd-reviewer.

---

## Incremental Review Detection

| Condition | Review Type |
|-----------|-------------|
| First iteration (no previous TDD_REVIEW.md) | Full |
| Previous verdict REJECTED | Full |
| Structural changes (sections added/removed/renumbered) | Full |
| Iteration ≥2 AND previous verdict CONDITIONAL/APPROVED | Delta (changed sections only) |

**Delta protocol:** Read previous TDD_REVIEW.md → diff current vs previous TDD → review ONLY changed sections for internal consistency, PRD traceability, security.

---

## Before Spawning

1. Grep TDD files for `TBD`, `TODO`, `pending` → if found: AskUserQuestion (human_in_loop) or log decision (auto). Do not spawn with unresolved decisions.

2. Mark TDDs as in_review:
```bash
python scripts/gate_transition.py {project} {slug} artifact "design/TDD.md" in_review
# Multi-TDD: run per file (TDD_MASTER.md, TDD_{NAME}.md)
```

3. Do NOT load TDD into parent context before spawning. Subagent reads fresh from disk.

4. Write `memory/features/{project}/{slug}/design_context.md`: tier, review mode (full|incremental), sections written (count + names), iteration N.

---

## Spawn tdd-reviewer Subagent

**Output:** `docs/features/{project}/{slug}/design/TDD_REVIEW.md`

**Build section manifest (before spawning):**

```bash
python -c "
import re
from pathlib import Path
for tdd in sorted(Path('docs/features/{project}/{slug}/design').glob('TDD*.md')):
    lines = tdd.read_text().split('\n')
    print(f'--- {tdd.name} ---')
    for i, line in enumerate(lines, 1):
        if re.match(r'^#{1,2}\s+', line):
            print(f'{i}: {line.strip()}')
"
```

```
Agent: tdd-reviewer | Model: haiku
Prompt:
"Execute per .claude/agents/tdd-reviewer.md definition.
Review Mode: {full|delta} | Tier: {tier}
Section manifest: {manifest}
Inputs: TDD path(s) via manifest offset/limit, PRD.md (Scope + NFR only), TDD_REVIEW.md (delta only)
Delta: changed sections only."
```

---

## Post-Review Validation

1. Verify `docs/features/{project}/{slug}/design/TDD_REVIEW.md` exists
2. Verify "Verdict:" in first 500 bytes
3. Missing/malformed → retry once, then escalate

---

## Verdict Handling

### APPROVED or CONDITIONAL

CONDITIONAL: log HIGH findings as tech debt, do not block.

```bash
# Mark review artifact:
python scripts/gate_transition.py {project} {slug} artifact "design/TDD_REVIEW.md" approved
# Mark TDD(s) — run per file:
python scripts/gate_transition.py {project} {slug} artifact "design/TDD.md" approved
# Multi-TDD: also run for TDD_MASTER.md, TDD_{NAME}.md
# Stage + pipeline phase:
python scripts/gate_transition.py {project} {slug} design-stage review approved
python scripts/gate_transition.py {project} {slug} design APPROVED
```

Auto-proceed to breakdown.

### REJECTED

1. Revert TDD status:
```bash
python scripts/gate_transition.py {project} {slug} artifact "design/TDD.md" draft
# Multi-TDD: run per affected file
```

2. Convergence check:
```bash
python scripts/convergence_check.py {slug} design --blocker-type "TDD_ISSUE|DESIGN_GAP" --findings '[{"section": "S3", "issue": "..."}]' --max-loops {max_loops}
```
Parse stdout: `{"verdict": "escalate"}` → report to human, stop. `{"verdict": "continue"}` → loop-back.

3. Classify and route:

| Blocker Type | Route To |
|--------------|----------|
| Any DESIGN_GAP | Write to `memory/features/{project}/{slug}/open_questions.md` → Architect (gaps only) |
| All TDD_ISSUE | Engineer (fix TDD_ISSUE blockers only) |
| Mixed | Architect first → Engineer |
