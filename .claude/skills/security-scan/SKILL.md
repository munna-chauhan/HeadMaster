---
name: security-scan
description: "Inline phase B of /execute. Runs diff_scanner.py against story branch. Reads JSON verdict. Never fixes."
argument-hint: <story-key> <slug> <branch> <base> <repo-path>
---

# Security Scan

Mechanical scan via Python. Claude reads verdict only. **Never fix.**

---

## Step 1: Run scanner

```bash
python3 scripts/diff_scanner.py \
  --branch story/{STORY-KEY} \
  --base {base_branch} \
  --repo {repo_path}
```

No changed files → PASS immediately.

---

## Step 2: Read JSON output

Extract: `verdict`, `secrets`, `sast`, `deps`, `changed_files`, `summary`

---

## Step 3: Write report

**Path:** `docs/features/{slug}/execution/reviews/security-scan-{STORY-KEY}.md`

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
