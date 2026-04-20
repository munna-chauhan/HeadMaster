# TDD Review: Inventory Management Service

**Reviewed By:** @tdd-reviewer (AI-Generated)
**Date:** 2026-03-23
**TDD Version:** 1.0
**Feature Folder:** docs/features/inventory-service

---

## 1. PRD Traceability

**Missing Features:** No issues found. All user stories and edge cases from the PRD are addressed by the TDD's data
models, API contracts, and error handling table.

**Edge Case Coverage:** All 5 confirmed edge cases from DISCOVERY_NOTES.md are covered:

- Empty result set → Section 7 integration test
- Mid-export failure → Section 5 failure taxonomy + Section 7 integration test
- Duplicate submission → Section 4 sequence diagram + Section 5 idempotency
- Shared S3 bucket → Section 6 config (`syndigo-exports-${ENVIRONMENT}`)
- JWT expiry → Implicitly handled — worker runs under service context, not user JWT

**Over-engineering:** No issues found. The TDD uses only existing infrastructure (DB, S3, Spring @Scheduled). No Kafka,
Redis, or other new dependencies introduced. Consistent with ADR-1.

**Verdict:** No issues found. Full PRD traceability confirmed.

---

## 2. SYSTEM_DESIGN_NOTES Compliance

- Section 1 (Architecture) aligns with "Architectural Pattern" from SYSTEM_DESIGN_NOTES.md (DB-backed async job queue).
- Section 4 (Sequence Diagram) matches the "Data Flow" from SYSTEM_DESIGN_NOTES.md steps 1–6.
- Section 5 (Resilience) implements the "Resilience Strategy" — 3x retry with exponential backoff, abort on S3 failure,
  1-hour timeout sweep.
- Section 6 (Observability) implements all metrics, tracing spans, and alerting thresholds from SYSTEM_DESIGN_NOTES.md "
  Observability Plan."
- Section 9 (ADRs) faithfully reproduces all 3 ADRs.

**Verdict:** No issues found. Full compliance with resolved architectural decisions.

---

## 3. Architecture & Data Stress Test

> **Severity:** medium
> **Section:** 3 (Data Models)
> **Issue:** Missing index on `export_jobs.status` for poller query
> **Detail:** The poller runs `SELECT ... WHERE status = 'PENDING'` every 5 seconds. The existing index
`idx_export_jobs_tenant_status` is a composite on `(tenant_id, status)`. For the poller query which does NOT filter by
> tenant_id, PostgreSQL may not use this index efficiently — it would need to scan all tenant partitions of the index.
> **Suggestion:** Add a dedicated single-column index: `CREATE INDEX idx_export_jobs_status ON export_jobs (status);`

**Scalability:** The batched read approach (10K per batch) with connection release between batches is sound. At 5
concurrent workers, worst case is 5 connections held intermittently — well within the 20-connection HikariCP pool.

**Pagination Stability:** No issues found — the `GET /api/v2/exports` list endpoint wasn't detailed in the TDD, but the
PRD specifies it only for "recent exports" per tenant. Since it queries by tenant_id with the composite index, this is
efficient.

---

## 4. Security & Constraints

No issues found:

- Tenant isolation enforced via `tenant_id` in all queries (Section 3 schema + Section 4 sequence).
- RBAC field filtering applied before serialization (inherited from existing ProductQueryService).
- Pre-signed URLs with 24-hour TTL (Section 6 config).
- No PII logged — job metadata only contains IDs, not product data.

---

## 5. Vertical Slice Critique

The 3 slices are **genuinely vertical and independent:**

- **Slice 1** delivers a working API that creates and tracks jobs — testable end-to-end without any export processing.
- **Slice 2** adds the core export pipeline (CSV only) — testable with a real file download from S3.
- **Slice 3** adds the second format and all safety rails — completes the feature.

Each slice can be merged and deployed independently. Slice 2 depends on Slice 1's DB schema and API, but that's a
natural vertical dependency, not a horizontal one.

**Verdict:** No issues found. Slices are well-structured.

---

## 6. Resolution Plan

### Must-Fix Blocker List

_(none)_

### High Priority

- [ ] Add single-column index on `export_jobs.status` for poller query efficiency (Finding #1)

### Risk Acceptance

_(none)_

### Verdict

**0 blockers. 1 high-priority recommendation (index addition).** TDD is approved to proceed to Epic/Task breakdown.
