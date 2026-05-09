# System Review Output Template

**Path:** `docs/features/{project}/{slug}/retrospective/system-review.md`

```markdown
# System Review: {slug}
**Date:** {ISO-date} | **Reviewer:** @review-agent (AI-Generated)
**Alignment Score:** {N}/10
**Execution Source:** JIRA_BREAKDOWN.md Execution Log
**TDD Reference:** {tdd_ref}

---

## Divergence Analysis

| # | Divergence | TDD Intent | Actual | Classification | Severity | Story |
|---|-----------|-----------|--------|----------------|----------|-------|
| 1 | {desc} | {TDD spec} | {actual} | Justified/Problematic | CRITICAL/HIGH/MEDIUM/LOW | {STORY-ID} |

---

## Root Cause Analysis

**Divergence {N}: {title}**
- Why: {root cause}
- Impact: {effect on quality/security/architecture}
- Evidence: {Execution Log entry or review artifact ref}
- Fix Required: YES / NO
- Fix: {what to change, which file, TDD section ref}

---

## Actionable Findings (orchestrator dispatches these)

<!-- MACHINE-PARSEABLE: orchestrator reads this table to dispatch fixes -->

| # | Story | Severity | Description | Fix Instructions |
|---|-------|----------|-------------|-----------------|
| 1 | {STORY-ID} | CRITICAL/HIGH | {what's wrong} | {what to fix} |

Only Problematic + CRITICAL/HIGH here. Justified + MEDIUM/LOW = informational only.

---

## Informational Findings

| # | Divergence | Classification | Severity | Notes |
|---|-----------|----------------|----------|-------|
| 1 | {desc} | Justified/Problematic | MEDIUM/LOW | {context} |

---

## Pipeline Improvements (write back to actual files)

### Skill Updates
- `implement/SKILL.md`: {specific change to add}
- `security-scan/SKILL.md`: {specific change}
- `review-code/SKILL.md`: {specific change}

### Agent Updates
- `.claude/agents/developer.md`: {constraint to add}
- `.claude/agents/review-agent.md`: {pattern to add}

### TDD Guidance (for next feature)
- {TDD section that needs more detail}
- {Pattern that should be documented}

---

## Summary

**Total Divergences:** {N}
**Justified:** {N} ({%})
**Problematic:** {N} ({%})
**Actionable (CRITICAL/HIGH):** {N}
**Alignment Score:** {N}/10
**Pipeline Health:** Healthy | Needs Attention | Critical

**Key Findings:**
- {finding 1 with impact}
- {finding 2 with impact}
```
