# REVIEW

**Pattern:** Direct (inline). Isolation via session boundary — this stage must run in a new Claude Code session from authoring. State detection (`planning_stages.draft = complete`) confirms readiness.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

---

## Route by gate mode

Read `gates.plan.review.mode` from config.yml:

| Mode | Behavior |
|------|----------|
| `skip` | Mark APPROVED immediately → gate, done |
| `auto` | Run prd-reviewer inline (Step 5 only) → auto-approve PASS/CONDITIONAL; REJECTED → escalate |
| `human_in_loop` | Steps 1–5 below |

---

## Steps (human_in_loop)

### Step 1 — Feedback gate

AskUserQuestion: "Do you have any feedback on the PRD?"
- Yes → apply feedback inline to PRD sections → restart Step 1
- No → Step 2

### Step 2 — Interactive Q&A

Read PRD section headings only (bash command below). Derive questions from actual PRD content — not a fixed template.

```bash
python -c "
import re
from pathlib import Path
lines = Path('docs/features/{project}/{slug}/planning/PRD.md').read_text().split('\n')
for i, l in enumerate(lines, 1):
    if re.match(r'^#{1,3} ', l): print(f'{i}: {l.strip()}')
"
```

Ask one AskUserQuestion per topic. Depth: s=3 questions, m=5, l=7.
Focus: scope boundaries, missing requirements, AC testability, assumptions that should be requirements.
After each answer → update PRD inline if correction needed.

### Step 3 — Open floor

AskUserQuestion: "Any other questions or concerns before we finalize?"
Discuss until user confirms done or skips.

### Step 4 — Optional sections gate

Ask each separately [Yes / No / Out of scope]:

1. "Should we add security requirements to the PRD?"
2. "Should we add observability / metrics targets?"
3. "Should we add performance SLOs?"

If Yes → load `.claude/agents/prd-author.md` inline, add section to PRD.
If No / Out of scope → skip. No N/A placeholder.

### Step 5 — Formal review (m/l tiers only; skip for xs/s)

Load `.claude/agents/prd-reviewer.md` inline.

Build section manifest:
```bash
python -c "
import re
from pathlib import Path
lines = Path('docs/features/{project}/{slug}/planning/PRD.md').read_text().split('\n')
for i, l in enumerate(lines, 1):
    if re.match(r'^#{1,2} ', l): print(f'{i}: {l.strip()}')
"
```

Pass to prd-reviewer: section manifest + PRD (read via manifest offsets). No full PRD in context.
Output: `docs/features/{project}/{slug}/planning/PRD_REVIEW.md`

**Post-review:**
- APPROVED / CONDITIONAL → proceed to gate
- CONDITIONAL → log HIGHs as tech debt to run-log.md
- REJECTED → fix BLOCKERs inline, re-run (max 2 iterations); if still REJECTED → escalate to human with blocker summary

---

## Gate

```bash
python scripts/gate_transition.py {project} {slug} plan-stage review approved
python scripts/gate_transition.py {project} {slug} planning APPROVED --artifact docs/features/{project}/{slug}/planning/PRD.md
```

Append to PRD.md header table: `PRD Status: APPROVED | {date} | iteration {N}`.
