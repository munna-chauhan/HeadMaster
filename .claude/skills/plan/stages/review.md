# REVIEW

**Pattern:** Launch `prd-reviewer` as isolated subagent. Fresh context — no authorship memory.

**Before spawning — mandatory context reset:**
```
/handoff
```
This clears the parent session context accumulated during Draft. The reviewer spawns clean with only the artifact paths — not the full PRD + DISCOVERY_NOTES the Draft stage already loaded.

**Output artifact:** `docs/features/{slug}/planning/PRD_REVIEW.md`

```
Agent: prd-reviewer
Model: haiku
Prompt:
"Respond concisely throughout.
Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths/commands exact.

Review PRD cold — no prior context on this feature.
Read as engineer implementing alone 6 months from now.

Inputs (read once, in order — STOP after step 2 unless C1/C2 fails):
1. docs/features/{slug}/planning/PRD.md — document under review
2. docs/features/{slug}/planning/DISCOVERY_NOTES.md — resolved decisions (source of truth)
3. docs/features/{slug}/planning/FEATURE_DRAFT.md — original vision (read ONLY if C1/C2 needs verification)

Do NOT read input/ folder. Do NOT read Jira/Confluence files.
If C1/C2 requires verifying a specific version number or field name:
  Read ONLY the specific file mentioned in PRD (e.g. FEATURE_DRAFT.md Section 2).
  Never read the entire input/ directory.

Execute every checklist item. Record PASS/FAIL/N/A before moving to next. No item skipped.

A — STRUCTURE
  A1 All tier-required sections present + populated (N/A+reason acceptable, empty = FAIL)
     Read complexity_tier from memory/features/{slug}/loop_state.json → lite=6, standard=10, full=14
  A2 No inline source annotations in body (no 'per Jira', 'as discussed', 'see Confluence')
  A3 No references to FEATURE_DRAFT.md or DISCOVERY_NOTES.md in PRD body
  A4 Open Questions section (if present per tier) contains only genuinely unresolved questions
  A5 Out of Scope items have justification
  A6 Header has Technical Owner + Confidence score

B — COMPLETENESS
  B1 Every discovery decision in DISCOVERY_NOTES reflected in FRs/NFRs/constraints
  B2 Every gap from FEATURE_DRAFT addressed or explicitly deferred in Open Questions (if section exists)
  B3 Every FR has at least one corresponding AC in Acceptance Criteria section
  B4 Concurrency/ordering/dedup edge case covered in at least one user story
  B5 Failure/offline/dependency-down scenario in NFRs or Risks & Mitigations (if section exists)
  B6 All repos mentioned have defined role (Repos section for full tier, or inline in FRs for lite/standard)
  B7 No open infrastructure questions blocking implementation

C — ACCURACY
  C1 Version numbers in PRD match FEATURE_DRAFT + raw inputs
  C2 Field names/API shapes in PRD match raw inputs (not just DISCOVERY_NOTES transcription)
  C3 Counts/limits/thresholds consistent across all PRD sections
  C4 All [Assumption] items have justification
  C5 No internal contradictions between sections

D — SELF-CONTAINEDNESS
  D1 Every FR implementable without opening any other document
  D2 Every NFR implementable without opening any other document
  D3 Every AC testable without opening any other document
  D4 Glossary defines all domain terms used in body

E — DEVELOPER FRICTION
  E1 Every metric has number + unit + percentile (not 'fast', 'large', 'soon')
  E2 Every AC starts with observable behavior, not implementation step
  E3 Error response schemas defined for all failure paths in FRs
  E4 Every FR answers: what to build, who uses it, when it triggers
  E5 Section 13 criteria measurable without author present

Severity per finding:
  BLOCKER — missing section, contradicts decision, unfeasible, blocks downstream design
  HIGH    — incomplete section, gap engineer must guess around
  MEDIUM  — inconsistency, minor gap, defer to TDD acceptable
  LOW     — typos, style, cleanup

Blocker type per finding:
  PRD_ISSUE      — PRD writing problem → fix in Draft
  DISCOVERY_GAP  — unresolved business rule → loop to Discover

Fix MEDIUM/LOW inline in PRD.md directly.
BLOCKER/HIGH → record in findings table, do not fix.

Write PRD_REVIEW.md with:
1. Executive Summary — verdict, blocker counts, strengths, critical gaps
2. Checklist Results — every item as PASS/FAIL/N/A
3. Traceability Matrix — every FR + NFR mapped to source (DISCOVERY_NOTES Q# or [Assumption])
4. Findings table:
   | # | Item | Severity | Type | Section | Issue | Fix |
5. Resolution Plan — blockers, high priority, acceptable risks, verdict

Verdict:
  APPROVED    — 0 BLOCKERs, 0 HIGHs
  CONDITIONAL — 0 BLOCKERs, HIGHs present (proceed after fixing HIGHs)
  REJECTED    — any BLOCKER present"
```

**On subagent return:**

**Post-subagent validation (mandatory before reading verdict):**
1. Verify file exists: `docs/features/{slug}/planning/PRD_REVIEW.md`
2. Verify file contains "Verdict:" in first 500 bytes
3. If missing or malformed → retry subagent once with same prompt, then escalate to human if still fails

If APPROVED or CONDITIONAL:

1. Append to PRD.md:
   ```
   ---
   PRD Status: APPROVED
   Approved: {ISO-date}
   Iterations: {N}
   ```
2. CONDITIONAL → log HIGH findings as tech debt, do not block progression
3. Update pipeline state:
   ```bash
   python3 scripts/gate_transition.py {slug} planning APPROVED --artifact docs/features/{slug}/planning/PRD.md
   ```

If REJECTED (any BLOCKER):

1. Emit gate failure metric:
   ```bash
   python3 scripts/metrics.py emit {slug} gate_fail --phase planning --stage Review --verdict REJECTED
   ```
2. **Run convergence check** — detects recurrence and oscillation before allowing loop-back:
   ```bash
   python3 scripts/convergence_check.py {slug} planning --blocker-type "PRD_ISSUE|DISCOVERY_GAP" --findings '[{"section": "S4", "issue": "..."}]' --max-loops {max_loops}
   ```
   Parse stdout JSON:
   - `{"verdict": "escalate", "reason": "..."}` → report reason to human, stop. Do NOT loop back.
   - `{"verdict": "continue", "iteration": N}` → proceed with loop-back below.

   The convergence checker will escalate immediately if:
   - A blocker that was previously resolved has recurred (oscillation)
   - The target stage (Discover/Draft) has been visited more than `max_loops` times
   - Total iterations exceed `max_loops`

3. **Auto-compress working files before loop-back** — reduces tokens on next Draft/Discover read:
   ```bash
   python .claude/hooks/write_compressor.py  # compresses memory files if above threshold
   ```
   Skip silently if files are below threshold or already compressed.
4. Any `DISCOVERY_GAP` blocker → write to `memory/features/{slug}/open_questions.md`, return to Discover
5. All `PRD_ISSUE` blockers → return to Draft
6. Mixed → Discover first, then Draft
