---
name: review-tdd
description: "Standalone TDD quality review. Checks completeness, consistency, implementability. No pipeline context required."
argument-hint: <tdd-path> [--prd <prd-path>]
---

# /review-tdd

Review a TDD file for quality and implementability. Standalone — works on any TDD, not just pipeline-generated ones.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

## Arguments

- `$1` — path to TDD file (required)
- `--prd` — path to PRD for traceability check (optional)

## Steps

### 1. Validate input

File exists and is `.md` → proceed. Otherwise → HALT.

Detect artifact type from content:

| Marker | Type |
|--------|------|
| `IMPLEMENTATION_BRIEF` in heading | xs brief (5 sections expected) |
| `TDD_MASTER` in heading | Master TDD (index + cross-cutting) |
| `## S1` or `## Section 1` | Standard TDD (count sections) |

### 2. Build section manifest

```bash
python -c "
import re
from pathlib import Path
text = Path('{tdd_path}').read_text()
for i, line in enumerate(text.split('\n'), 1):
    if re.match(r'^#{1,2}\s+', line):
        print(f'{i}: {line.strip()}')
"
```

### 3. Section-by-section review

Load `.claude/agents/tdd-reviewer.md` constraints. Agent methodology governs.

Read one section at a time via offset/limit → review → write findings → discard raw content before next section.

**Checklist per section:**

| Check | Detail |
|-------|--------|
| Completeness | ≥5 lines of substantive content (not just headings/blanks) |
| Specificity | No banned vague language ("appropriate", "as needed", "standard approach") |
| Typed contracts | All interfaces have typed fields, request/response shapes, error codes |
| Consistency | Cross-references between sections resolve correctly |
| Implementability | Could an engineer implement from this section alone without guessing? |

### 4. PRD traceability (if --prd provided)

Read PRD Scope + NFR sections only (by heading grep). Check:
- Every PRD functional requirement maps to a TDD interface or component
- Every PRD NFR maps to a TDD capacity/validation section
- Missing mappings → `[PRD Gap]`

### 5. Output

```markdown
## TDD Review: {filename}

**Type:** {type} | **Sections:** {N} | **Lines:** {N}

### Findings
| # | Section | Severity | Issue | Fix |
|---|---------|----------|-------|-----|

### Section Health
| Section | Status | Notes |
|---------|--------|-------|

### PRD Traceability
{N/A if no PRD provided, or gap list}

### Summary
BLOCKER: {N} | HIGH: {N} | MEDIUM: {N} | LOW: {N}

**Verdict:** {APPROVED | CONDITIONAL | REJECTED}
```
