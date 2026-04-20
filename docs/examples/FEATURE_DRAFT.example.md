---
feature:
  slug: inventory-export-api
  name: Async Inventory Export API
  type: feature
  description: Asynchronous job-based export system for large product datasets via S3
  owner: jane.smith@company.com
  created: 2026-03-15
  project: platform
jira:
  epic_key: PROJ-1234
  story_keys: [ PROJ-1235, PROJ-1236 ]
status:
  current_phase: F1
  last_updated: 2026-03-15
---

**Technical Owner:** Jane Smith (jane.smith@company.com)
**AI Co-Author:** @requirements-analyst (AI-Generated)
**Date:** 2026-03-15
**Pipeline Version:** 2.0.0
**Feature Folder:** docs/features/inventory-export-api

---

# Feature: Async Inventory Export API

## 1. High-Level Goal

Product managers need to export large datasets (50K–500K products) for offline analysis, partner data feeds, and
compliance audits. The current UI "Download CSV" button times out beyond ~5K rows due to synchronous processing on the
API gateway, forcing users into manual pagination workarounds or direct database queries via support tickets.

We need an asynchronous job-based export system: users submit an export request with filters, receive a job ID, and poll
or receive a webhook callback when the file is ready for download from S3.

---

## 2. Raw Context & Notes

**User Narrative:**
The sync export endpoint has been a pain point for 6+ months. PMs are doing manual workarounds. We need async exports
with S3 delivery, RBAC enforcement, and webhook callbacks. Must not break the existing v1 endpoint.

**Known Constraints:**

- Must not degrade primary read path performance
- Existing `ExportController` v1 endpoint must remain operational during migration
- RBAC must match UI behavior (tenant isolation, role-based field visibility)
- Pre-signed S3 URL TTL configurable, default 24 hours

**Referenced Materials:**

- Jira: PROJ-1234 (epic), PROJ-1235 (API design), PROJ-1236 (worker implementation)
- Confluence: page 98765 (export architecture), page 98766 (S3 conventions)
- Code: `distribution-services/.../ExportController.java`, `distribution-services/.../ProductQueryService.java`

---

## 3. Business Value & Requirements

**Problem Statement:** Synchronous export times out at ~5K rows. Users resort to manual workarounds or support tickets
for large exports. Estimated 3 hours/week lost per PM.

**Target Users:**

- Internal: Product managers, data analysts, compliance team
- External: Partner integrations consuming product feeds

**Success Criteria:**

- Export 500K rows without timeout or primary read path degradation
- Job completion notification via polling or webhook
- Pre-signed S3 URL delivered within 5 minutes for 500K row export (p95)
- Zero regression on existing v1 sync endpoint

**Acceptance Criteria (from PROJ-1234):**

- `POST /api/v2/exports` accepts filter params, returns `job_id`
- `GET /api/v2/exports/{job_id}` returns status (PENDING, PROCESSING, COMPLETED, FAILED, EXPIRED)
- Completed job returns pre-signed S3 URL with configurable TTL
- RBAC filters applied identically to UI behavior
- CSV and JSON Lines output formats supported

---

## 4. Existing System Touchpoints

**Integration Points:**

- `ProductQueryService` (`distribution-services/.../ProductQueryService.java`) — synchronous JDBC cursor-based query
  engine. Supports pagination, not streaming. Will need batched approach (10K rows/batch) or new streaming method.
- `ExportController` (`distribution-services/.../ExportController.java`) — current sync CSV endpoint. Must remain
  operational. New async endpoint is additive at `/api/v2/exports`.
- `TenantContextFilter` (`common-lib/.../TenantContextFilter.java`) — extracts tenant ID from JWT. Must be reused for
  RBAC in async worker context.
- `S3StorageService` (`infra-lib/.../S3StorageService.java`) — existing S3 upload/download utility. Supports multipart
  upload. Reuse directly.

**Patterns to Follow:**

- Async job pattern already used in `ReportGenerationService` — follow same job state machine (PENDING → PROCESSING →
  COMPLETED/FAILED)
- S3 key convention from Confluence page 98766: `{service}/{tenant_id}/{job_id}/{filename}`

---

## 5. Data Model Implications

**New Tables:**

- `export_jobs` — tracks job state: `job_id (UUID PK)`, `tenant_id`, `status`, `filters (JSONB)`, `output_format`,
  `s3_key`, `expires_at`, `created_at`, `completed_at`

**New S3 Structure:**

- Key convention: `exports/{tenant_id}/{job_id}/{filename}`
- Lifecycle policy needed: auto-delete after TTL expiry (not yet defined — see Gaps)

**No changes** to existing product tables. Export reads from read replicas only.

---

## 6. Conflicts & Migration Concerns

**Breaking Changes:** None. New endpoint is additive (`/api/v2/exports`). v1 sync endpoint unchanged.

**Legacy Compatibility:**

- `ProductQueryService` is synchronous — streaming 500K rows requires batched fetch (10K at a time) or a new streaming
  query method. Batched approach preferred to avoid refactoring shared service.
- Worker must reuse `TenantContextFilter` logic — cannot assume JWT context exists in async thread. Tenant ID must be
  passed explicitly to worker.

**Migration Path:**

1. Deploy async endpoint alongside v1 (no cutover required)
2. Update client integrations to use v2 over 2-sprint period
3. Deprecate v1 after all clients migrated (tracked in PROJ-1240)

---

## 7. Identified Gaps

**Gap: S3 lifecycle policy undefined**
Impact: Exported files accumulate indefinitely, increasing storage costs.
Resolution: Define retention policy in discovery (time-based vs TTL-based auto-delete).

**Gap: Webhook MVP scope unclear**
Impact: Affects API contract and worker complexity. Polling-only is simpler but less useful for partner integrations.
Resolution: Confirm with PM whether webhooks are MVP or Phase 2 in discovery Q&A.

**Gap: Rate limiting not specified**
Impact: A user could submit 100 concurrent export jobs, saturating the worker pool.
Resolution: Define per-tenant concurrent export limit and queue depth in discovery.

**Gap: Compression requirements unstated**
Impact: 500K row CSV uncompressed could be 500MB+. gzip would reduce to ~50MB but adds worker CPU.
Resolution: Confirm default compression behavior and whether user can opt out.

---

## 8. Open Questions

**P0 (Blockers):**

- [ ] **Q1:** Are webhook callbacks in MVP scope or Phase 2? Determines API contract and worker design.
- [ ] **Q2:** What is the per-tenant concurrent export limit? Determines worker pool sizing and queue design.

**P1 (Critical):**

- [ ] **Q3:** What is the S3 lifecycle retention policy? Time-based (e.g., 7 days) or TTL from job creation?
- [ ] **Q4:** Should exports be gzip-compressed by default? User opt-out supported?

**P2 (Nice-to-have):**

- [ ] **Q5:** Should export job history be retained indefinitely or pruned after N days?
- [ ] **Q6:** Is there a hard file size limit, or do we rely on S3's 5TB object limit?

---

**Next Phase:** F2: Discovery (`/plan inventory-export-api`)

1. Review Gaps and Open Questions above
2. Run: `/plan inventory-export-api`
