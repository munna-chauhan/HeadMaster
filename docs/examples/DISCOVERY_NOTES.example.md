# Discovery Notes: Inventory Export Service

**Technical Owner:** Jane Smith (jane.smith@company.com)  
**AI Co-Author:** @requirements-analyst (AI-Generated)
**Date:** 2026-03-15  
**Feature Folder:** docs/features/inventory-export

---

## Discovery Summary

This document captures the results of systematic discovery conducted through interactive Q&A, targeting implementation
gaps identified in FEATURE_DRAFT.md.

**Questions Asked:** 6 primary + 2 follow-ups = 8 total  
**Priority Breakdown:**

- **P0 REQUIRED (3)**: Export format strategy, concurrency limits, tenant isolation
- **P1 OPTIONAL (2)**: Webhook notifications, file retention policy
- **P2 OPTIONAL (1)**: Performance SLOs

**Resolution Status:** All questions answered, 1 blocking action item identified (see section below)

---

## Business Rules

### Q1: Export Output Formats & Compression

**Category:** Business Rules  
**Priority:** P0 Blocker  
**Status:** ✅ Resolved

**Question:**  
What export formats should be supported? Should files be compressed?

**Answer:** **CSV and JSON Lines, gzip compression mandatory**

**Implementation Details:**

- Formats: CSV (headers + data rows), JSON Lines (one JSON object per line)
- Compression: All exports gzip-compressed (`.gz` extension)
- Content-Type: `application/gzip` for downloads
- No Excel/Parquet support in MVP

**Rationale:**  
CSV covers majority use case (spreadsheet import). JSON Lines supports programmatic processing (stream-friendly). Gzip
reduces S3 storage costs by ~70% and download bandwidth.

**Trade-offs:**

- ✅ **Simplicity**: Only 2 formats, no complex Excel libraries
- ✅ **Cost**: 70% storage reduction via compression
- ⚠️ **User Experience**: Users must decompress before opening (acceptable for MVP)

---

### Q2: Tenant Concurrency Limits

**Category:** Business Rules  
**Priority:** P0 Blocker  
**Status:** ✅ Resolved

**Question:**  
How many concurrent export jobs should a single tenant be allowed?

**Answer:** **3 concurrent jobs per tenant**

**Implementation Details:**

- Check: Query `export_jobs` table for `tenant_id` WHERE `status IN (PENDING, PROCESSING)`
- Limit: If count >= 3, return HTTP 429 with `Retry-After: 60` header
- Tracking: Decrement counter when job transitions to `COMPLETED` or `FAILED`

**Rationale:**  
Prevents single tenant from monopolizing worker threads. 3 allows small teams to run multiple exports in parallel (e.g.,
different product categories) without blocking each other.

**Trade-offs:**

- ✅ **Fairness**: No tenant can starve others
- ✅ **Simplicity**: Easy to implement (simple count query)
- ⚠️ **Large Tenants**: May frustrate high-volume users (acceptable for MVP, can add tier-based limits later)

**Follow-up Q2.1: Concurrency Enforcement Granularity**

**Question:** Should limit be per-tenant or per-user within tenant?

**Answer:** **Per-tenant** (not per-user)

**Rationale:** Simplifies implementation. Users within same tenant coordinate via team communication. Per-user limits
add complexity (user assignment, role mapping) without clear MVP value.

---

### Q3: Tenant Isolation & RBAC

**Category:** Security  
**Priority:** P0 Blocker  
**Status:** ✅ Resolved

**Question:**  
How should tenant isolation and role-based field visibility be enforced?

**Answer:** **JWT-based tenant isolation + RBAC field filtering**

**Implementation Details:**

- Tenant Isolation: `TenantContextFilter` extracts `tenant_id` from JWT, query filters by
  `product.tenant_id = :tenantId`
- RBAC Field Filtering: `RolePermissionService.getVisibleFields(role)` → exclude hidden fields from CSV columns / JSON
  properties
- Example: If role cannot see `cost_price` field in UI, exclude from export output

**Rationale:**  
Reuse battle-tested `TenantContextFilter` (100% coverage across existing endpoints). RBAC field filtering ensures data
governance consistency between UI and exports.

**Trade-offs:**

- ✅ **Security**: Zero risk of cross-tenant data leakage
- ✅ **Consistency**: Export respects same RBAC rules as UI
- ⚠️ **Performance**: Field filtering adds per-row overhead (acceptable for async exports)

---

## Integration

### Q4: Webhook Notifications on Completion

**Category:** Integration  
**Priority:** P1 Optional  
**Status:** ✅ Resolved

**Question:**  
Should the system send webhook notifications when exports complete?

**Answer:** **No webhooks in MVP. Polling only.**

**Implementation Details:**

- MVP: Users poll `GET /api/v1/exports/{jobId}` for status updates
- Status transitions: `PENDING` → `PROCESSING` → `COMPLETED`/`FAILED`
- Response includes `download_url` when status = `COMPLETED`

**Rationale:**  
Webhooks add complexity (callback URL registration, retry logic, failure handling) without clear MVP demand. Polling
sufficient for initial release. Deferred to Phase 2 based on user feedback.

**Trade-offs:**

- ✅ **Simplicity**: No webhook infrastructure (queue, retry, DLQ)
- ✅ **Security**: No callback URL validation needed
- ⚠️ **UX**: Requires client-side polling (acceptable for MVP)

---

## Performance & Capacity

### Q5: File Retention Policy

**Category:** Performance & Capacity  
**Priority:** P1 Optional  
**Status:** ✅ Resolved

**Question:**  
How long should export files and job metadata be retained?

**Answer:** **30 days retention, then auto-pruned**

**Implementation Details:**

- Job metadata: Delete rows from `export_jobs` WHERE `completed_at < NOW() - INTERVAL 30 DAY`
- S3 files: Delete objects via S3 lifecycle policy (expire after 30 days)
- Cleanup: Scheduled job runs daily at 2 AM UTC (low-traffic window)

**Rationale:**  
30 days balances user convenience (re-download window) with storage costs. S3 lifecycle policy automates cleanup without
application logic.

**Trade-offs:**

- ✅ **Cost Control**: Automatic cleanup prevents unbounded S3 growth
- ✅ **Compliance**: Aligns with data retention policies
- ⚠️ **User Impact**: Files inaccessible after 30 days (acceptable, users can re-export)

---

### Q6: Performance SLOs & Capacity Targets

**Category:** Performance & Capacity  
**Priority:** P2 Informational  
**Status:** ✅ Resolved

**Question:**  
What are the performance SLO targets for export jobs?

**Answer:** **Job completion within 5 minutes for 95% of exports**

**Implementation Details:**

- Target: p95 completion time < 5 minutes (for typical datasets: <100K rows)
- Timeout: Jobs not completed within 60 minutes marked `FAILED`, partial file deleted
- Worker threads: 10 concurrent workers (configurable via `export.worker.pool.size`)

**Rationale:**  
5-minute SLO provides "fast enough" user experience for async operation. 60-minute timeout prevents zombie jobs from
holding resources.

**Trade-offs:**

- ✅ **User Experience**: 5 minutes feels responsive for large datasets
- ✅ **Resource Management**: Timeout prevents runaway jobs
- ⚠️ **Large Datasets**: 500K+ rows may exceed 5-minute target (acceptable outlier)

**Follow-up Q6.1: Worker Thread Scaling**

**Question:** Should worker count auto-scale based on queue depth?

**Answer:** **Fixed worker pool for MVP** (no auto-scaling)

**Rationale:** Kubernetes HPA can scale pods based on queue depth. In-app auto-scaling adds complexity without clear
benefit. Fixed pool (10 workers) sufficient for MVP traffic estimates.

---

## Edge Cases

### Confirmed Edge Case Handling:

1. **Empty result set:** Export completes with status `COMPLETED`. File contains only headers (CSV) or empty file (JSON
   Lines). `file_size_bytes = 0`.

2. **Mid-export failure (DB connection drop):** Job marked `FAILED`. Partial file deleted from S3. User can retry by
   submitting new export request.

3. **Duplicate submission:** If user submits identical export request while one is `PROCESSING`, return existing
   `job_id` instead of creating duplicate. Prevents duplicate work.

4. **JWT expiry during long export:** Export runs under service account context after initial auth validation. JWT
   expiry does NOT cancel running export.

5. **Tenant with no products:** Same as empty result set (status `COMPLETED`, zero-byte file).

---

## Identified Gaps (None)

All implementation gaps from FEATURE_DRAFT.md were resolved during discovery. No additional gaps identified.

---

## Blocking Action Items

**Must complete before Phase F3 (Create PRD):**

### 1. Audit Existing TenantContextFilter Coverage

**Owner:** Security Team / Jane Smith  
**Priority:** P0 Blocker  
**Deadline:** Before PRD creation

**Scope:**

- Verify `TenantContextFilter` applies to ALL product-related queries
- Audit: `ProductQueryService.findByFilters()` for missing `tenant_id` clauses
- Test: Cross-tenant query attack simulation (user A cannot see user B's data)

**Deliverable:** Security audit report confirming 100% tenant isolation coverage

**Status:** ⚠️ **BLOCKING PRD** - Must complete before documenting API contracts in PRD

---

## Key Decisions Summary

**Quick Reference:**

| Decision              | Choice                                          | Rationale                                                |
|-----------------------|-------------------------------------------------|----------------------------------------------------------|
| **Export Formats**    | CSV + JSON Lines (gzip compressed)              | Covers 90% use cases, reduces storage costs by 70%       |
| **Concurrency Limit** | 3 jobs per tenant                               | Prevents resource monopolization, simple to implement    |
| **Tenant Isolation**  | JWT-based (TenantContextFilter)                 | Reuses battle-tested pattern, zero cross-tenant risk     |
| **RBAC Enforcement**  | Field-level filtering via RolePermissionService | Consistent with UI data governance                       |
| **Webhooks**          | Not in MVP (polling only)                       | Deferred to Phase 2, reduces complexity                  |
| **File Retention**    | 30 days (S3 lifecycle policy)                   | Balances convenience with cost control                   |
| **Performance SLO**   | p95 < 5 minutes, 60-minute timeout              | Fast enough for async, prevents zombie jobs              |
| **Worker Scaling**    | Fixed pool (10 workers)                         | Kubernetes HPA handles pod scaling, no in-app complexity |

---

## Resolution Status

**All Questions Resolved:** ⚠️ **NO** (1 blocking audit required)

**Blockers for F3 (Create PRD):**

1. ⚠️ **TenantContextFilter Audit** — Must verify 100% tenant isolation coverage before PRD

**Can Proceed With:**

- Export format design (resolved)
- Concurrency limits (resolved)
- File retention policy (resolved)
- Performance SLOs (resolved)

**Post-PRD Validations:**

- Load testing to validate 5-minute p95 target
- Security penetration testing (cross-tenant isolation)

---

## Next Steps

1. ⏸️ **PAUSE**: Complete TenantContextFilter audit (1-2 days, blocking)
2. 📧 Request security team audit report
3. ⏭️ **After audit complete**: Proceed to F3 (Create PRD)
4. 💾 Extract key decisions to `.claude/memory/inventory-export/decisions.md`

---

**Discovery Phase Status:** ⚠️ **Blocked on Audit** (1 blocker identified)  
**Estimated Audit Duration:** 1-2 days  
**Next Phase:** F3 (Create PRD) — **Ready to start after audit complete**
