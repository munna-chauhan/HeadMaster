# ENGINEER

**Pattern:** Direct. Load `.claude/agents/tdd-author.md` for behavioral constraints before executing.

**On loop-back entry:** read loop_state.json → convergence already validated by `convergence_check.py` before dispatch.
Read `blocker_history` to understand which TDD_ISSUE blockers recurred vs. new — fix only current findings from TDD_REVIEW.md.

**Gate conditions (standard/full tier):**
- `Architecture Locked: YES` in SYSTEM_DESIGN_NOTES.md
- PRD.md exists

**Gate conditions (lite tier):**
- PRD.md exists (SYSTEM_DESIGN_NOTES.md not required — not produced for lite)

**Inputs (read once, in order):**
1. `docs/features/{slug}/planning/PRD.md` — requirements, NFRs, ACs
2. `docs/features/{slug}/design/SYSTEM_DESIGN_NOTES.md` — ADRs, data flow, resilience, observability, interface contracts (source of truth). **Skip for lite tier.**

Never read: FEATURE_DRAFT.md, DISCOVERY_NOTES.md, input/, CODE_ANALYSIS.md, API_CONTRACTS.md — all distilled into SYSTEM_DESIGN_NOTES.

---

## TDD Split Decision

**Skip for lite tier** — lite always produces a single IMPLEMENTATION_BRIEF.md.

**Decide before writing anything (standard/full tier only).**

Count repos from SYSTEM_DESIGN_NOTES.md (authoritative). SYSTEM_DESIGN_NOTES.md S1 is the final answer.

**Single repo → one file:** `design/TDD.md — all sections`
**Multiple repos → master + per-repo:**
```
design/TDD_MASTER.md        — cross-cutting (sections 1, 2, 8, 9, 10, 11)
design/TDD_{REPO_NAME}.md   — repo-specific (sections 3, 4, 5, 6, 7) per repo
```

---

## TDD Structure

**Section count depends on complexity_tier (from loop_state.json):**

### Tier: Lite (5 sections → IMPLEMENTATION_BRIEF.md)

Write `docs/features/{slug}/design/IMPLEMENTATION_BRIEF.md` directly:

1. **Scope & Approach** — what changes + how (1 paragraph each)
2. **Data Models & Contracts** — schema changes, API shapes, request/response
3. **Component Changes** — files to modify, new files, method signatures (no bodies)
4. **Testing Strategy** — what to test, how, edge cases
5. **Delivery Slice** — single slice with ACs mapped to components

Gate: 5 sections present, interfaces typed. No TDD review subagent — proceed directly to breakdown.

### Tier: Standard (8 sections → TDD.md)

1. **Architecture Overview** — pattern, tech stack per repo
2. **Domain & Module Structure** — bounded contexts, module boundaries
3. **Data Models & Contracts** — SQL DDL, API schemas, event schemas
4. **Component Design & Command Lifecycle** — class responsibilities, method signatures
5. **Error Handling & Resilience** — failure taxonomy, retry params, circuit breakers
6. **Testing Strategy** — unit/integration/edge tests, Given/When/Then
7. **Vertical Delivery Slices** — 3-5 end-to-end shippable slices
8. **ADRs** — from SYSTEM_DESIGN_NOTES verbatim + implementation details

Gate: 8 sections present, slices defined, interfaces typed.

### Tier: Full (11 sections → TDD.md)

1. **Architecture Overview** — use `/draw` for architecture diagrams, never Mermaid
2. **Domain & Module Structure** — bounded contexts, directory tree (feature-driven)
3. **Data Models & Contracts** — SQL DDL, API schemas from SYSTEM_DESIGN_NOTES S3, event schemas, config templates
4. **Component Design & Command Lifecycle** — class responsibilities, method signatures, sequence diagram
5. **Error Handling & Resilience** — failure taxonomy, implement SYSTEM_DESIGN_NOTES resilience exactly
6. **Observability & Configuration** — implement exact metric/span names from SYSTEM_DESIGN_NOTES S10
7. **Testing Strategy** — unit/integration/perf/edge tests, Given/When/Then
8. **Vertical Delivery Slices** — 3-5 end-to-end shippable slices with PRD stories, components, ACs, SP
9. **ADRs** — from SYSTEM_DESIGN_NOTES verbatim + implementation details. Flag `[DESIGN GAP]` if gap found.
10. **Resource Requirements** — memory/CPU/storage sized to NFR thresholds
11. **Deployment Architecture** — platform, model, IaC snippet, health checks, rollback

**Constraints:**
- No executable code — contracts only
- Every interface traces to PRD. Missing → `[PRD Gap]`
- Honor ADRs — immutable. Disagree → `[DESIGN GAP]`
- Vertical slices by feature, not technology tier
- Complete error taxonomy — all HTTP codes per endpoint, exception types per method

**MIGRATION_PLAN.md (conditional)**
Check SYSTEM_DESIGN_NOTES S11:
- N/A or "no migration required" → skip
- Actual migration strategy → write `docs/features/{slug}/design/MIGRATION_PLAN.md`

**Gate (per tier):**
- Lite: 5 sections in IMPLEMENTATION_BRIEF.md → COMPLETE (skip Review, proceed to breakdown)
- Standard: 8 sections in TDD.md → proceed to Review
- Full: 11 sections in TDD.md → proceed to Review
