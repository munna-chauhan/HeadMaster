# REVIEW

**Pattern:** `prd-reviewer` subagent. Isolated — no authorship memory.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

**When to run:**

1. **Check tier workflow** (`.claude/workflows/{tier}.yml` → `stages.prd_review.status`):
   - `skip` → skip review entirely, mark PRD as APPROVED, advance to design
   - `optional` → proceed to step 2 (check gates.plan_review)
   - `required` → proceed to step 2 (check gates.plan_review)

2. **Check `gates.plan.review.mode`** in config.yml:

   | Mode | Behavior |
   |------|----------|
   | `human_in_loop` | Alignment session (see below) → spawn prd-reviewer → present findings → human approval |
   | `auto` | Spawn prd-reviewer → PASS/CONDITIONAL auto-approve; REJECTED + convergence fail → escalate. Log to run-log.md |
   | `skip` | Mark PRD APPROVED immediately. Log skip reason. Advance to design |

### Alignment Session (`human_in_loop` only, before reviewer spawn)

Read PRD section headings + first 3 lines per section (Read with offset/limit). Do NOT load full PRD.

Walk through with human (max 3 rounds, AskUserQuestion per round):

| Round | Question |
|-------|----------|
| 1 — Scope | "IN: [...]. OUT: [...]. Correct?" |
| 2 — Requirements | "NFRs: [...]. Assumptions: [...]. Missing or wrong?" |
| 3 — Integrations | "Systems: [...]. Missing constraints?" |

Human corrects → update PRD inline → next round. All confirmed → spawn reviewer.
Discard extracted points after alignment.

---

**Pre-spawn checklist:**

1. Incremental detection: if iteration > 1 → `python scripts/diff_review_filter.py {prd_path}` (exit 0 = incremental, else full)
2. Resolve P0/P1 open items from `draft_context.md` via AskUserQuestion
3. Write `draft_context.md`: tier, review_mode, iteration N
4. Do NOT load PRD into parent context

**Build section manifest + spawn:**

```bash
python -c "
import re
from pathlib import Path
lines = Path('docs/features/{project}/{slug}/planning/PRD.md').read_text().split('\n')
for i, line in enumerate(lines, 1):
    if re.match(r'^#{1,2}\s+', line): print(f'{i}: {line.strip()}')
"
```

**Output:** `docs/features/{project}/{slug}/planning/PRD_REVIEW.md`

```
Agent: prd-reviewer | Model: haiku
Prompt:
"Execute per .claude/agents/prd-reviewer.md definition.
Review Mode: {full|incremental} | Tier: {tier}
Section manifest: {manifest}
Inputs: PRD.md (read via manifest offset/limit), FEATURE_DRAFT.md (fact-check only)
Incremental: changed sections only, skip A1."
```

**Post-subagent validation:**
1. Verify `PRD_REVIEW.md` exists + contains "Verdict:" in first 500 bytes
2. Missing/malformed → retry once, then escalate to human

**If APPROVED/CONDITIONAL:**

1. Human approval already handled in "When to run" step 2 based on gates.plan_review mode
2. Append gate string to PRD.md: `PRD Status: APPROVED`, date, iterations
3. CONDITIONAL → log HIGHs as tech debt
4. `python scripts/gate_transition.py {project} {slug} planning APPROVED --artifact docs/features/{project}/{slug}/planning/PRD.md`

**If REJECTED:**

1. Check iteration count in loop_state.json
2. If iterations > 2 → ESCALATE to human:
   ```
   PRD review REJECTED after 2+ iterations. Findings:
   {blocker summary}
   
   Options:
   - Accept PRD as-is (mark APPROVED, log risks)
   - Manual fix specific sections
   - Re-run discovery for missing context
   ```
3. If iterations ≤ 2 AND findings are formatting/minor → fix and re-run review
4. If iterations ≤ 2 AND findings are CONTENT gaps → attempt to fill from existing inputs (FEATURE_DRAFT.md, DISCOVERY_NOTES.md, input/*.md). If gaps remain after attempt → ESCALATE to human.
