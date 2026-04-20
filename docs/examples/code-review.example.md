# Code Review: Inventory Management Service — Slice 1

**Reviewed By:** @review-agent (AI-Generated)
**Date:** 2026-03-28
**Feature Folder:** docs/features/inventory-service
**TDD Reference:** TDD.md (Slice 1: Core Job Lifecycle)

---

### Stats

- **Files Modified:** 2
- **Files Added:** 8
- **Files Deleted:** 0
- **Lines + / -:** 487 / 12

### Summary

Slice 1 implements the core job lifecycle — DB migration, entity, repository, service, and controller. The code is
clean, well-structured, and follows existing project conventions. Two issues found: one high-severity SQL injection risk
in the filter handling, and one medium-severity missing validation.

### TDD Compliance

Implementation matches the TDD blueprint. The `export_jobs` schema matches Section 3. The API endpoints and response
shapes match Section 3 contracts. The `ExportService` concurrency check and duplicate detection logic match Section 4
sequence. One deviation: the controller uses `@PathVariable` instead of the `@RequestParam` shown in the TDD for the
list endpoint — this is acceptable as it follows the project's existing REST conventions.

---

### Findings

> **Severity:** high
> **File:** `distribution-services/src/main/java/com/syndigo/export/repository/ExportJobRepository.java`
> **Line:** 34
> **Issue:** Raw string interpolation in native query allows SQL injection
> **Detail:** The `findByFilters` method concatenates user-provided filter values directly into a native SQL string:
`"WHERE filters @> '" + filtersJson + "'"`. If `filtersJson` contains a crafted payload, this is exploitable.
> **Suggestion:** Use a parameterized query with `@Param`:
> ```java
> @Query(value = "SELECT * FROM export_jobs WHERE filters @> CAST(:filters AS jsonb)", nativeQuery = true)
> List<ExportJob> findByFilters(@Param("filters") String filtersJson);
> ```

> **Severity:** medium
> **File:** `distribution-services/src/main/java/com/syndigo/export/api/ExportV2Controller.java`
> **Line:** 47
> **Issue:** No validation on `format` field in CreateExportRequest
> **Detail:** The `format` field is a raw String. If a user sends `"format": "XLSX"`, the request is accepted and a job
> is created with an unsupported format. It will fail at processing time instead of at submission time.
> **Suggestion:** Change `format` to the `ExportFormat` enum in the DTO and add `@Valid` to the controller parameter.
> Spring will return 400 automatically for invalid enum values.

**Verification:**

- Ran `./mvnw test -pl distribution-services` — 47/47 tests pass.
- Ran `./mvnw compile` — no compilation errors.
- The SQL injection finding was confirmed by manually crafting a filter payload in a test.

---

### Verdict

Found **1 high** and **1 medium** issue. The high-severity SQL injection must be fixed before merge. Run
`/code-review-fix` to address findings.
