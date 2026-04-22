# REVIEW

**Pattern:** `prd-reviewer` subagent. Isolated — no authorship memory.

**Before spawning:**

1. Write `memory/features/{slug}/draft_context.md`: tier, sections written, key decisions, open items, iteration N.
2. Do NOT load PRD.md into parent context before spawning (isolation via minimal parent state, not /handoff)

**Output:** `docs/features/{slug}/planning/PRD_REVIEW.md`

```
Agent: prd-reviewer
Model: haiku
Prompt:
"Terse. Fragments OK. Tables over prose. Code/paths exact.

Review PRD cold — read as engineer implementing alone 6 months from now.

Inputs (read once):
1. docs/features/{slug}/planning/PRD.md
2. docs/features/{slug}/planning/DISCOVERY_NOTES.md — source of truth
3. docs/features/{slug}/planning/FEATURE_DRAFT.md — original vision
4. docs/features/{slug}/input/*.md — for C1/C2 verification only. Never raw .json.

Execute every item. Record PASS/FAIL/N/A.

A — STRUCTURE
  A1 All tier-required sections present + populated (N/A+reason OK, empty = FAIL)
     Tier from memory/features/{slug}/loop_state.json → lite=6, standard=10, full=14
  A2 No inline source annotations ('per Jira', 'as discussed', 'see Confluence')
  A3 No references to FEATURE_DRAFT.md or DISCOVERY_NOTES.md in body
  A4 Open Questions (if present) = genuinely unresolved only
  A5 Out of Scope items have justification
  A6 Header uses standard PRD header table (Technical Owner, Status, Date, Approver required)

B — COMPLETENESS
  B1 Every FR has ≥1 AC
  B2 Concurrency/ordering/dedup edge case in ≥1 user story
  B3 Failure/dependency-down scenario in NFRs or Risks
  B4 All repos have defined role
  B5 No open infra questions blocking implementation
  B6 All external dependencies identified (APIs, services, teams)

C — ACCURACY (Self-Contained Validation)
  C1 Counts/limits/thresholds consistent across sections
  C2 All [Assumption] items justified
  C3 No internal contradictions (between FRs, NFRs, ACs)
  C4 Version numbers/API shapes internally consistent (no cross-file validation)
  C5 All technical terms defined in Glossary or inline

D — SELF-CONTAINEDNESS
  D1 Every FR implementable without other docs
  D2 Every NFR implementable without other docs
  D3 Every AC testable without other docs
  D4 Glossary defines all domain terms

E — DEVELOPER FRICTION
  E1 Every metric has number + unit + percentile
  E2 Every AC starts with observable behavior
  E3 Error response schemas for all failure paths
  E4 Every FR: what to build, who uses it, when it triggers
  E5 Acceptance criteria measurable without author present

Severity: BLOCKER (blocks design) | HIGH (engineer must guess) | MEDIUM (defer to TDD OK) | LOW (style)
Blocker type: PRD_ISSUE → Draft | DISCOVERY_GAP → Discover

Fix MEDIUM/LOW inline in PRD.md. BLOCKER/HIGH → findings table only.

Write PRD_REVIEW.md:
1. Executive Summary — verdict + blocker counts
2. Checklist Results — every item PASS/FAIL/N/A
3. Traceability Matrix — FR/NFR → source (DISCOVERY_NOTES Q# or [Assumption])
4. Findings: | # | Item | Severity | Type | Section | Issue | Fix |
5. Verdict + resolution plan

Verdict: APPROVED (0 blocker, 0 high) | CONDITIONAL (0 blocker, highs present) | REJECTED (any blocker)"
```

**Post-subagent validation:**
1. Verify `PRD_REVIEW.md` exists + contains "Verdict:" in first 500 bytes
2. Missing/malformed → retry once, then escalate to human

**If APPROVED/CONDITIONAL:**

1. Append gate string to PRD.md: `PRD Status: APPROVED`, date, iterations
2. CONDITIONAL → log HIGHs as tech debt
3. `python3 scripts/gate_transition.py {slug} planning APPROVED --artifact docs/features/{slug}/planning/PRD.md`

**If REJECTED:**

1. Run convergence check:
   ```bash
   python3 scripts/convergence_check.py {slug} planning --blocker-type "PRD_ISSUE|DISCOVERY_GAP" --findings '[...]' --max-loops {max_loops}
   ```
   `escalate` → stop, report to human. `continue` → proceed below.
3. `DISCOVERY_GAP` → Discover. `PRD_ISSUE` → Draft. Mixed → Discover first.
