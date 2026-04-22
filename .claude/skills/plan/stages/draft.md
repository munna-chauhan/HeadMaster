# DRAFT

**Pattern:** Direct. Load `.claude/agents/prd-author.md`.

**On loop-back:** read `loop_state.json` → fix flagged sections only. Convergence already validated.

**Pre-conditions:** FEATURE_DRAFT.md exists + DISCOVERY_NOTES.md ends with `All Questions Resolved: YES`.
Missing → halt, return to Init/Discover.

**Inputs (read once):** FEATURE_DRAFT.md → DISCOVERY_NOTES.md → `input/*.md` (fallback, prefer `.md` over `.json`).

**Write** `docs/features/{slug}/planning/PRD.md`

Header: standard PRD header table from SKILL.md (Status: Draft).

**Sections by tier** (from `loop_state.json`):

### Full (14 sections)
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
12. **Repos** — name, role, tech stack, build command
13. **Acceptance Criteria** — feature pass/fail for sign-off
14. **Appendix** — glossary, links

### Standard (10) — sections: 1, 2, 4, 5, 6, 7, 8, 9, 11, 13

### Lite (6) — sections: 1, 4, 5, 6, 9, 13

**Rules:**
- **Single source of truth:** PRD must be self-contained. No cross-references to FEATURE_DRAFT, DISCOVERY_NOTES, or input files in body.
- No omissions (N/A + reason if empty)
- No source annotations ('per Jira', 'as discussed in Confluence', 'see FEATURE_DRAFT')
- All technical terms defined in Glossary or inline
- Diagrams only when clearer than prose:

| Type           | When                       | Tool                                    |
|----------------|----------------------------|-----------------------------------------|
| User/process   | >3 steps with branches     | Mermaid (simple) or `/draw` (complex)   |
| System context | services + external actors | `/draw`                                 |
| Gantt/phasing  | 3+ phases                  | Mermaid `gantt`                         |
| State machine  | status transitions         | Mermaid (simple) or `/draw` (many)      |

Mermaid inline ≤5 nodes only. Never for architecture diagrams.

**NO_PRIOR_KNOWLEDGE_TEST:** Could an unfamiliar engineer implement from PRD alone? If no → add context.

**Gate:** All tier-required sections present, metrics quantified → advance to Review.

```bash
python3 scripts/gate_transition.py {slug} planning Review --artifact docs/features/{slug}/planning/PRD.md
```
