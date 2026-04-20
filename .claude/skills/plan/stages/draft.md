# DRAFT

**Pattern:** Direct. Load `.claude/agents/prd-author.md` for behavioral constraints before executing.

**On loop-back entry:** read loop_state.json → convergence already validated by `convergence_check.py` before dispatch.
Read `blocker_history` to understand which blockers recurred vs. which are new — fix only current findings.

**Gate conditions (before starting):**

- FEATURE_DRAFT.md exists
- DISCOVERY_NOTES.md ends with `All Questions Resolved: YES`
- Missing → halt, return to Init/Discover

**Inputs (read once, in order):**

1. FEATURE_DRAFT.md — vision + gaps
2. DISCOVERY_NOTES.md — resolved decisions
3. `input/` — fallback only. Prefer `.md` extracted files over raw `.json` (extractor runs during Init).

On loop-back: read loop_state findings. Fix flagged sections only.

**Write** `docs/features/{slug}/planning/PRD.md`

Header:

```
**Technical Owner:** {from FEATURE_DRAFT.md}
**AI Co-Author:** Product Analyst (AI-Generated)
**Date:** {ISO-date}
**Feature Folder:** docs/features/{slug}
**Confidence:** {1-10}/10 — {rationale for downstream design success}
```

**Section count depends on complexity_tier (from loop_state.json):**

### Tier: Full (14 sections)
1. **Executive Summary** — 3-5 sentences: overview, users, value, MVP
2. **Background & Business Context** — problem, pain, why now
3. **Goals & Success Metrics** — quantified ("export -40%", "p99 < 200ms")
4. **Functional Requirements** — FR-1, FR-2... no source annotations
5. **Non-Functional Requirements** — Perf/Reliability/Security/Scale, quantified
6. **User Stories** — INVEST-compliant, testable ACs, cover concurrency/ordering/dedup
7. **Assumptions & Constraints** — `[Assumption]` + justification
8. **Dependencies** — systems, teams, approvals, APIs
9. **Out of Scope** — exclusions + justification
10. **Open Questions** — genuinely unresolved only
11. **Risks & Mitigations** — business + technical
12. **Repos** — name, role, tech stack, build command (one row per repo)
13. **Acceptance Criteria** — feature pass/fail for sign-off
14. **Appendix** — glossary, links

### Tier: Standard (10 sections)
1. **Executive Summary**
2. **Background & Business Context**
3. **Functional Requirements**
4. **Non-Functional Requirements**
5. **User Stories**
6. **Assumptions & Constraints**
7. **Dependencies**
8. **Out of Scope**
9. **Risks & Mitigations**
10. **Acceptance Criteria**

### Tier: Lite (6 sections)
1. **Executive Summary**
2. **Functional Requirements**
3. **Non-Functional Requirements**
4. **User Stories**
5. **Out of Scope**
6. **Acceptance Criteria**

Rules: no omissions (N/A + reason if empty), no source annotations in body, no references to FEATURE_DRAFT.md or
DISCOVERY_NOTES.md anywhere in PRD, diagrams only when clearer than prose.

**Diagram decision rule:**

| Diagram type             | When to use                | Tool                                                        |
|--------------------------|----------------------------|-------------------------------------------------------------|
| User flow / process flow | >3 steps with branches     | Mermaid `flowchart` (simple) or `/draw` (complex branching) |
| System context           | services + external actors | `/draw` — layout matters                                    |
| Gantt / phasing          | S12 roadmap with 3+ phases | Mermaid `gantt` only                                        |
| State machine            | status transitions         | Mermaid `stateDiagram` (simple) or `/draw` (many states)    |

Use `/draw {slug} "{diagram description}"` → saves to `docs/features/{slug}/diagrams/`.
Use Mermaid inline only for simple linear flows (≤5 nodes, no crossing arrows).
Never use Mermaid for architecture or multi-service diagrams — arrows always messy.

**NO_PRIOR_KNOWLEDGE_TEST:** Could engineer unfamiliar with codebase implement from PRD alone? If no → add context.

**Gate:** All tier-required sections present, no source annotations, all metrics quantified → proceed to Review.
(lite=6, standard=10, full=14 — per complexity_tier in loop_state.json)
