# SYSTEM_DESIGN_NOTES Section Structure

13 sections (all required, N/A + reason if not applicable):

1. **Bounded Context** — verified repos, classes, blast radius, existing patterns (from subagent findings)
2. **Architectural Pattern** — chosen pattern, justification, alternatives rejected
3. **Interface Contracts** — all new/modified endpoints/events with request/response schemas, field types, validation rules, error codes
4. **Data Flow** — step-by-step with verified class names + Mermaid diagram
5. **Threat Model** — STRIDE table with mitigations per threat
6. **NFR Validation** — PRD NFR vs design capacity vs 10x load
7. **Dependency Map** — external systems, SLAs, rate limits, failure modes
8. **ADRs** — one per major decision (context, options, decision, rationale). Immutable once written.
9. **Resilience Strategy** — retries, circuit breakers, idempotency per integration point
10. **Observability Plan** — metric names, span names, alert thresholds
11. **Migration/Rollout Strategy** — approach summary (detail in MIGRATION_PLAN.md at Engineer stage)
12. **Remaining Risks** — accepted risks + mitigation plan
13. **Architecture Status** — gate string: `Architecture Locked: YES`
