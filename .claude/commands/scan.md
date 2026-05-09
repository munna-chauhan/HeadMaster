---
name: scan
description: "Security scanning. Pick capabilities: secrets, sast, deps, iac, licenses, auth, pentest, compliance. Comma-separated. Each runs mechanical scan + AI analysis."
argument-hint: <capabilities> [--scope diff|full|staged] [--repo <path>] [--branch <branch>] [--base <base>]
---

# /scan

Pick what to scan. Comma-separated. Each capability runs two layers:
1. **Mechanical** — Python scripts, fast, deterministic (regex, CLI tools, CVE databases)
2. **Intelligence** — AI reads mechanical results + source code, applies judgment (context, data flow, business impact, false positive filtering)

## Capabilities

| Capability | Mechanical Layer | Intelligence Layer |
|---|---|---|
| `secrets` | Regex pattern match (API keys, passwords, private keys) | Assess context: is this a real secret or a variable name/test fixture/placeholder? Trace where the value flows |
| `sast` | bandit (Python), eslint-security (JS/TS) | Cross-file data flow: does user input reach SQL/command/template without sanitization? Logic vulnerabilities: race conditions, TOCTOU, privilege escalation through business logic |
| `deps` | pip-audit, npm audit, OWASP dependency-check | Assess reachability: is the vulnerable code path actually used by this project? Prioritize by business impact |
| `iac` | checkov/tfsec on Terraform, CloudFormation, K8s | Evaluate blast radius: what does this misconfiguration expose? Is it mitigated by network policy or other controls? |
| `licenses` | License string matching against blocked/warning/ok lists | Assess usage: is the copyleft dependency linked or just a dev tool? Does the project license conflict? |
| `auth` | Pattern match for auth decorators/middleware on routes | Evaluate auth model: is the auth check correct for this resource? Does horizontal access control exist? Can a user access another user's data? |
| `pentest` | Attack surface enumeration (endpoints, inputs, integrations) | OWASP ASVS checklist (A01-A10) with contextual analysis. CWE Top 25 mapping. Assess business impact per finding |
| `compliance` | Git history secret scan, lock file checks, version pinning | SLSA supply chain assessment. Evaluate overall security posture. Prioritize remediation by risk |
| `all` | Every capability above | Full intelligence pass across all findings |

## Scope

| Scope | What files | Default |
|---|---|---|
| `diff` | Changed files between `--branch` and `--base` | ✅ default |
| `full` | All tracked files in repo | — |
| `staged` | Staged files only (pre-commit) | — |
| `--pr` | Shortcut: `--scope diff --branch feature/{slug} --base main` | — |

## Arguments

| Argument | Default | Description |
|---|---|---|
| capabilities | required | Comma-separated list, or `all` |
| `--scope` | `diff` | `diff`, `full`, or `staged` |
| `--repo` | active project root | Repo path or project name from config.yml |
| `--branch` | current branch | Source branch (diff scope) |
| `--base` | `main` | Base branch (diff scope) |
| `--pr` | false | Merge gate shortcut |

## Repo Resolution

1. `--repo /absolute/path` → use directly
2. `--repo project-name` → look up `projects.{name}.root` in config.yml
3. No `--repo` → active project root from config.yml

---

## Execution

### Step 1: Parse capabilities

Split input on commas. `all` expands to every capability.

### Step 2: Mechanical layer

Run `diff_scanner.py` with appropriate scope:

```
python .claude/skills/security-scan/scripts/diff_scanner.py --repo {repo} [--branch X --base Y | --full | --staged]
```

Focused modes if only specific capabilities requested:
- `deps` only → `--deps-only`
- `iac` only → `--iac-only`

Collect JSON results.

### Step 3: Intelligence layer

Per capability, AI analyzes mechanical results + reads relevant source code per Intelligence Layer column in Capabilities table.

Per finding, classify: `CONFIRMED` | `FALSE_POSITIVE` | `NEEDS_REVIEW`. Filter FALSE_POSITIVEs from verdict (keep in report for audit trail).

For `pentest`: load `.claude/agents/references/owasp-checklist.md`.

### Step 4: Write report

**Path:** `docs/features/{project}/{slug}/execution/security-scan-{ISO-date}.md`

**Structure:** Header (repo, date, scope, verdict) → per-capability section (mechanical findings, AI assessment, confirmed issues table, filtered false positives) → summary table (capability × raw → confirmed → verdict) → prioritized remediation list.

### Step 5: Verdict

Final verdict = worst across all CONFIRMED findings (FALSE_POSITIVE excluded).

| Finding | Verdict |
|---|---|
| Confirmed secret or CRITICAL CVE/SAST | BLOCKED |
| HIGH severity (confirmed) | WARNING |
| MEDIUM/LOW or unreachable | PASS (noted) |
| Tool unavailable | PASS (noted, check skipped) |

If `pipeline.dry_run: true` → run scan, write report, do not block pipeline.
