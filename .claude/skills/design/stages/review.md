# REVIEW

**Pattern:** Launch `tdd-reviewer` as isolated subagent. Fresh context — no authorship memory.

**Before spawning — mandatory context reset:**
```
/handoff
```
Clears parent context accumulated during Engineer stage. Reviewer spawns clean.

**Note:** This review stage runs for standard and full tiers only. Lite tier skips review entirely.
For standard tier (8 sections): items referencing S9-S11 should be marked N/A.
For full tier (11 sections): all items apply.

**Output artifact:** `docs/features/{slug}/design/TDD_REVIEW.md`

```
Agent: tdd-reviewer
Model: haiku
Prompt:
"Respond concisely throughout.
Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths/commands exact.

Review TDD cold — no prior context on this feature.
Read as engineer implementing alone.

Inputs (read once, in order):
1. docs/features/{slug}/design/TDD.md — single repo
   OR TDD_MASTER.md + all TDD_{REPO}.md files found in docs/features/{slug}/design/ — multi-repo
2. docs/features/{slug}/planning/PRD.md
3. docs/features/{slug}/design/SYSTEM_DESIGN_NOTES.md
4. docs/features/{slug}/design/MIGRATION_PLAN.md — read if exists, skip if absent

Execute every checklist item. Record PASS/FAIL/N/A. No item skipped.

A — PRD TRACEABILITY
  A1 Every PRD user story → TDD component or API endpoint
  A2 Every PRD NFR → TDD S10 resource requirements sized accordingly
  A3 Every PRD AC → testable via TDD design
  A4 Every edge case from PRD S4/S5 → TDD S7 test specification
  A5 No over-engineering — no tech not in PRD/design

B — DESIGN COMPLIANCE
  B1 Architectural pattern from SYSTEM_DESIGN_NOTES S2 reflected in TDD S1
  B2 Data flow from SYSTEM_DESIGN_NOTES S4 aligned with TDD S4 sequence diagram
  B3 Resilience strategy from SYSTEM_DESIGN_NOTES S9 implemented exactly in TDD S5
  B4 Observability plan from SYSTEM_DESIGN_NOTES S10 — exact metric/span names in TDD S6
  B5 Threat model mitigations from SYSTEM_DESIGN_NOTES S5 → security controls in TDD S5
  B6 Every ADR from SYSTEM_DESIGN_NOTES S8 reflected in TDD S9 — no contradictions
  B7 Interface contracts from SYSTEM_DESIGN_NOTES S3 implemented exactly in TDD S3

C — ARCHITECTURE STRESS TEST
  C1-C9: N+1 queries, missing pagination, missing indexes, unbounded memory, transactions spanning external calls, missing isolation levels, deadlock potential, synchronous loops, missing connection pooling

D — SECURITY AUDIT
  D1-D9: Missing authz, multi-tenancy filters, PII exposure, input validation, rate limiting, authentication, encryption, secrets management, audit logging

E — VERTICAL SLICE CRITIQUE
  E1-E4: End-to-end functional, independently deliverable, mapped to business value, no incomplete dependencies

Severity: BLOCKER | HIGH | MEDIUM | LOW
Blocker type: TDD_ISSUE (fix in Engineer) | DESIGN_GAP (loop to Architect)

Fix MEDIUM/LOW inline in TDD files directly.
BLOCKER/HIGH → record in findings table only, do not fix.

Write TDD_REVIEW.md:
1. Executive Summary — verdict, blocker counts by type
2. PRD Traceability — per A1-A5
3. Design Compliance — per B1-B7
4. Architecture Stress Test — per C1-C9
5. Security Audit — per D1-D9
6. Vertical Slice Critique — per E1-E4
7. Resolution Plan — blockers, verdict

Verdict:
  APPROVED    — 0 BLOCKERs, 0 HIGHs
  CONDITIONAL — 0 BLOCKERs, HIGHs present
  REJECTED    — any BLOCKER present"
```

**On subagent return:**

**Post-subagent validation (mandatory before reading verdict):**
1. Verify file exists: `docs/features/{slug}/design/TDD_REVIEW.md`
2. Verify file contains "Verdict:" in first 500 bytes
3. If missing or malformed → retry subagent once with same prompt, then escalate to human if still fails

If APPROVED or CONDITIONAL:

1. Update loop_state: `{"design": {"iteration": N, "status": "PASS"}}`
2. CONDITIONAL → log HIGH findings as tech debt, do not block progression
3. Update pipeline state:
   ```bash
   python3 scripts/gate_transition.py {slug} design APPROVED --artifact docs/features/{slug}/design/TDD_REVIEW.md
   ```
4. Proceed to `/breakdown {slug}`

If REJECTED:

1. **Run convergence check:**
   ```bash
   python3 scripts/convergence_check.py {slug} design --blocker-type "TDD_ISSUE|DESIGN_GAP" --findings '[{"section": "S3", "issue": "..."}]' --max-loops {max_loops}
   ```
   Parse stdout JSON:
   - `{"verdict": "escalate", "reason": "..."}` → report reason to human, stop.
   - `{"verdict": "continue", "iteration": N}` → proceed with loop-back below.

3. Any `DESIGN_GAP` → write to `memory/features/{slug}/open_questions.md`, return to Architect
4. All `TDD_ISSUE` → return to Engineer
5. Mixed → Architect first, then Engineer
