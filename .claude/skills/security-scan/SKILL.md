---
name: security-scan
description: "Security scan skill. Runs diff_scanner.py against a branch diff — secrets, SAST, CVEs. Embedded in Phase A of /execute. Never fixes."
argument-hint: <story-key> <slug> <branch> <base> <repo-path>
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Security Scan

Mechanical scan via Python. Claude reads verdict only. **Never fix.**

---

## Step 1: Run scanner

```bash
python .claude/skills/security-scan/scripts/diff_scanner.py \
  --branch story/{STORY-KEY} \
  --base {base_branch} \
  --repo {repo_path}
```

No changed files → PASS immediately.

---

## Step 2: Read JSON output

Extract: `verdict`, `secrets`, `sast`, `deps`, `iac`, `licenses`, `auth`, `changed_files`, `summary`

---

## Step 3: Write report

**Path:** `docs/features/{project}/{slug}/execution/reviews/security-scan-{STORY-KEY}.md`

```markdown
# Security Scan: {STORY-KEY}
Verdict: {PASS|BLOCKED|WARNING} | {ISO-datetime}

## Changed Files
{list}

## Secrets
{PASS | findings with file:line}

## SAST
{PASS | WARNING | findings}

## Dependencies
{PASS | WARNING | BLOCKED | findings}

## IaC
{PASS | WARNING | BLOCKED | findings with file:line, rule, severity | SKIPPED: reason}

## Licenses
{PASS | WARNING | BLOCKED | findings: package@version → license (verdict, source) | SKIPPED: reason}

## Auth Routes
{PASS | WARNING | BLOCKED | findings with file:line, route, framework, confidence | framework_detected}

## Summary
{one line from JSON}
```

---

## Verdict rules

| Finding            | Verdict      |
|--------------------|--------------|
| Any secret         | BLOCKED      |
| CRITICAL CVE       | BLOCKED      |
| HIGH SAST/dep      | WARNING      |
| MEDIUM/LOW         | PASS (noted) |
| No tools available | PASS (noted) |
| No files           | PASS         |

BLOCKED → return to implement with findings.
WARNING → log, proceed to review-code.
