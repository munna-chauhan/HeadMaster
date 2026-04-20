# System Design Notes: Inventory Management Service

**Date:** 2026-03-20
**Feature Folder:** docs/features/inventory-service
**Parent PRD:** PRD.md

## Bounded Context

- **Primary repository:** `distribution-services` (Java 17, Spring Boot 3.2)
- **Shared library:** `common-lib` (TenantContextFilter, RBAC utilities)
- **Infrastructure library:** `infra-lib` (S3StorageService)
- **Directories in scope:**
    - `distribution-services/src/main/java/com/syndigo/export/` (NEW — all export domain code)
    - `distribution-services/src/main/java/com/syndigo/api/ExportController.java` (MODIFY — add v2 endpoints)
    - `distribution-services/src/main/resources/db/migration/` (NEW — Flyway migration for export_jobs table)

## Architectural Pattern

**Async Job Queue via database polling.** We chose a DB-backed job table over a message queue (SQS/Kafka) because:

1. The expected throughput is low (tens of exports per hour, not thousands per second).
2. A DB table gives us queryable job state for the status API with zero additional infrastructure.
3. The team has no operational experience with SQS in this codebase — introducing it for a low-volume feature is
   over-engineering.

A `@Scheduled` Spring poller picks up PENDING jobs every 5 seconds and dispatches them to a bounded thread pool.

## Data Flow

1. User sends `POST /api/v2/exports` with filters and format.
2. `ExportController` validates auth (TenantContextFilter), checks concurrency limit (max 3 per tenant), inserts a
   PENDING row into `export_jobs`, returns `202 Accepted` with the job ID.
3. `ExportJobPoller` (Spring @Scheduled, 5s interval) picks up PENDING jobs, sets them to PROCESSING, dispatches to
   `ExportWorker` thread pool (size: 5).
4. `ExportWorker` calls `ProductQueryService` in batches of 10K rows, serializes each batch to the target format,
   gzip-compresses, and streams via multipart upload to S3.
5. On completion, `ExportWorker` updates the job row to COMPLETED with the S3 key and pre-signed URL.
6. User polls `GET /api/v2/exports/{jobId}` to check status and retrieve the download URL.

## Architecture Decision Records

### ADR-1: DB-backed job queue over SQS

- **Context:** Need async job processing for export requests.
- **Options Considered:** A) SQS with Lambda consumer — scales automatically, decoupled | B) DB table with Spring
  poller — simple, queryable, no new infra
- **Decision:** Option B — DB-backed job table.
- **Rationale:** Low volume (tens/hour), team has zero SQS operational experience, and the status API needs queryable
  job state anyway. Adding SQS would require a DLQ, IAM policies, and monitoring — all overhead for a feature that
  processes ~50 jobs/day.

### ADR-2: Batched JDBC reads over streaming cursor

- **Context:** Need to read up to 500K rows without OOM.
- **Options Considered:** A) JDBC streaming cursor (forward-only ResultSet) — memory-efficient but holds a DB connection
  for the entire export duration | B) Batched pagination (OFFSET/LIMIT 10K) — more DB round-trips but releases
  connections between batches
- **Decision:** Option B — Batched pagination.
- **Rationale:** Holding a connection for 5–10 minutes during a 500K export would exhaust the connection pool (max 20).
  Batched reads release the connection after each 10K fetch. The overhead of repeated queries is acceptable given the
  async nature.

### ADR-3: Gzip at application level, not S3

- **Context:** Files must be gzip-compressed.
- **Options Considered:** A) Compress in-app before upload | B) Upload uncompressed, use S3 object lambda to compress on
  download
- **Decision:** Option A — Application-level gzip.
- **Rationale:** S3 Object Lambda adds latency and cost per download. Pre-compressing means the file is stored
  compressed, reducing S3 storage costs and download time. The CPU cost of gzip on the export worker is negligible.

## Resolved Trade-Offs

| # | Trade-Off               | Options Presented                              | User's Choice | Rationale                              |
|---|-------------------------|------------------------------------------------|---------------|----------------------------------------|
| 1 | Job queue mechanism     | SQS (scalable) vs DB poller (simple)           | DB poller     | Low volume, no new infra               |
| 2 | Read strategy           | Streaming cursor (efficient) vs Batched (safe) | Batched       | Connection pool safety                 |
| 3 | Compression layer       | App-level vs S3 Object Lambda                  | App-level     | Lower cost, simpler                    |
| 4 | Worker thread pool size | 3 (conservative) vs 10 (aggressive)            | 5             | Balance between throughput and DB load |

## Resilience Strategy

- **Failure Modes:**
    - DB connection loss during batch read: Retry current batch 3 times with exponential backoff. If all retries fail,
      mark job FAILED, delete partial S3 file.
    - S3 upload failure: Abort multipart upload, mark job FAILED.
    - Worker thread crash: Unhandled exception caught by thread pool, job marked FAILED.
- **Idempotency:** Duplicate export requests (same tenant + same filters + PROCESSING status) return the existing job
  ID.
- **Circuit Breakers:** Not needed for MVP — the bounded thread pool (size 5) naturally limits blast radius.

## Observability Plan

- **Metrics:**
    - `export.jobs.submitted` (counter, tagged by tenant_id and format)
    - `export.jobs.completed` (counter, tagged by tenant_id, format, and duration_bucket)
    - `export.jobs.failed` (counter, tagged by tenant_id and failure_reason)
    - `export.batch.read.duration` (timer, per 10K batch)
    - `export.s3.upload.duration` (timer, per multipart chunk)
- **Tracing:**
    - Span: `export.job.process` (root span for entire job lifecycle)
    - Span: `export.batch.query` (child span per 10K batch read)
    - Span: `export.s3.upload` (child span for S3 multipart upload)
- **Alerting:**
    - Alert if `export.jobs.failed` rate exceeds 10% over a 15-minute window.
    - Alert if any single export job exceeds 30 minutes processing time.

## Technology Choices

- **Spring Boot 3.2** @Scheduled for job polling
- **HikariCP** connection pool (existing, max 20 connections)
- **AWS SDK v2** for S3 multipart upload (existing in `infra-lib`)
- **Flyway** for DB migration (existing)
- **Micrometer** for metrics (existing)
- **OpenTelemetry** for tracing spans (existing)

## Remaining Risks

- **Read replica lag:** Accepted for MVP. Export API response will document "data reflects eventual consistency."
- **Connection pool pressure under concurrent exports:** 5 worker threads each holding a connection during batch reads
  could consume 25% of the pool. Monitoring will detect if this becomes a problem.

---
**Architecture Locked: YES**
