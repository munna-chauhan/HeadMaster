# JIRA_BREAKDOWN Template

## File Header

```markdown
# Jira Breakdown: {Feature Name}
Date: {ISO-date} | Agent: release-agent | Epic: {EPIC_KEY} | Project: {project_key}
Stories: {N} | Points: {N} SP | Critical Path: {N} SP

> LOCAL IDs only. After Jira push: update JIRA ID column with real keys.

---

## Story Overview

| LOCAL ID | JIRA ID | Epic | Repo | Title | SP | Priority | Parallel Group | Blocked By |
|----------|---------|------|------|-------|----|----------|----------------|------------|

> Story status tracked in `loop_state.json stories.{KEY}.status`. Execute owns all transitions.

---

## Dependency Graph

```mermaid
graph TD
    {story deps}
```
Critical Path: {STORY-XX → ...} ({N} SP) | Parallel Opportunities: {groups}

---

## Stories
```

## Per-Story Format

| Field | Value |
|-------|-------|
| Heading | `### {LOCAL-ID}: {Behavior-focused title}` |
| Metadata line 1 | SP: {N} \| Priority: P0/P1/P2 \| Parallel Group: {N \| None} |
| Metadata line 2 | Epic: {key} \| Repo: {repo} \| Labels: `area/{repo}` `priority/p{n}` `effort/{n}sp` |
| Metadata line 3 | PRD: S{N} \| TDD: Slice {N} |
| What | One sentence — behavior delivered |
| Why | One sentence — why it matters |
| AC happy path | GIVEN {context} WHEN {action} THEN {outcome} (numbered list) |
| AC error/edge | GIVEN {invalid/missing/boundary} WHEN {action} THEN {error behavior} (numbered list) |
| AC error note | Minimum 1 error AC per story. None → "No error paths — pure config/wiring change." |
| Test Strategy | `{unit \| integration \| e2e \| mock-integration} — {1-line reason}` |
| Dev Notes — Files to modify | Exact paths from TDD |
| Dev Notes — Files to create | New files if any |
| Dev Notes — Key changes | Function signatures, new endpoints, schema changes, config entries |
| Dev Notes — Depends on | Libraries, APIs, services — flag unfamiliar with `⚠️ UNFAMILIAR` |
| Dev Notes — Merged from | Absorbed slices or None |
| Dev Notes — ⚠️ Complex | If 5 SP: explain why it can't be split |
| Links | Blocked By: {STORY-XX \| None} \| Blocks: {None} \| Related: {None} |

## Execution Log (after all stories)

```markdown
## Execution Log

| Metric | Value |
|--------|-------|
| Total stories | {N} |
| Total SP | {N} |
| ⏳ NEW | {N} |
| ⬆️ EXISTING | {N} |
| ✅ COMPLETE (skip) | {N} |
| Parallel groups | {N} |
```
