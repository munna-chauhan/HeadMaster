#!/usr/bin/env python3
"""
diff_scanner.py — scan git diff for secrets, SAST issues, vulnerable deps.

Usage:
    python3 scripts/diff_scanner.py --branch story/KEY --base feature/slug --repo /path/to/repo
    python3 scripts/diff_scanner.py --staged --repo /path/to/repo

Output: JSON to stdout
{
  "verdict": "PASS" | "BLOCKED" | "WARNING",
  "secrets": [...],
  "sast": [...],
  "deps": [...],
  "changed_files": [...],
  "summary": "one line"
}
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add repo root to path so secret_scanner is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.secret_scanner import scan_file


def run(cmd: list[str], cwd: str = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
        return r.returncode, r.stdout, r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, "", str(e)


def get_changed_files(branch: str, base: str, repo: str, staged: bool) -> list[str]:
    if staged:
        _, out, _ = run(["git", "diff", "--cached", "--name-only"], cwd=repo)
    else:
        _, out, _ = run(["git", "diff", "--name-only", f"{base}...{branch}"], cwd=repo)
    return [f.strip() for f in out.splitlines() if f.strip()]


def scan_secrets(files: list[str], repo: str) -> list[dict]:
    findings = []
    for f in files:
        full = str(Path(repo) / f)
        for finding in scan_file(full):
            findings.append({
                "file": f,
                "line": finding.line_num,
                "pattern": finding.pattern_name,
                "snippet": finding.snippet,
            })
    return findings


def _tool_available(name: str) -> bool:
    """Check if a CLI tool is on PATH."""
    import shutil
    return shutil.which(name) is not None


def scan_sast(files: list[str], repo: str) -> list[dict]:
    findings = []
    unavailable = []
    py_files = [f for f in files if f.endswith(".py")]
    js_files = [f for f in files if f.endswith((".js", ".ts", ".jsx", ".tsx"))]

    if py_files:
        if not _tool_available("bandit"):
            unavailable.append("bandit (pip install bandit) — Python SAST skipped")
        else:
            code, out, _ = run(["bandit", "-f", "json", "-q"] + py_files, cwd=repo)
            if out.strip():
                try:
                    data = json.loads(out)
                    for r in data.get("results", []):
                        if r.get("issue_severity") in ("HIGH", "MEDIUM"):
                            findings.append({
                                "tool": "bandit",
                                "file": r.get("filename", ""),
                                "line": r.get("line_number", 0),
                                "severity": r.get("issue_severity"),
                                "issue": r.get("issue_text", ""),
                            })
                except json.JSONDecodeError:
                    pass

    if js_files:
        if not _tool_available("npx"):
            unavailable.append("npx/eslint (install Node.js) — JS/TS SAST skipped")
        else:
            code, out, _ = run(
                ["npx", "eslint", "--format=json", "--plugin=security"] + js_files,
                cwd=repo
            )
            if out.strip():
                try:
                    for file_result in json.loads(out):
                        for msg in file_result.get("messages", []):
                            if msg.get("severity", 0) >= 2:
                                findings.append({
                                    "tool": "eslint",
                                    "file": file_result.get("filePath", ""),
                                    "line": msg.get("line", 0),
                                    "severity": "HIGH",
                                    "issue": msg.get("message", ""),
                                })
                except json.JSONDecodeError:
                    pass

    # Attach unavailable tool notices as INFO findings so caller can surface them
    for notice in unavailable:
        findings.append({"tool": "unavailable", "severity": "INFO", "issue": notice, "file": "", "line": 0})

    return findings


def scan_deps(files: list[str], repo: str) -> list[dict]:
    findings = []
    unavailable = []
    dep_files = {Path(f).name for f in files}

    if "requirements.txt" in dep_files or "setup.py" in dep_files:
        if not _tool_available("pip-audit"):
            unavailable.append("pip-audit (pip install pip-audit) — Python dep scan skipped")
        else:
            code, out, _ = run(["pip-audit", "--format=json", "-r", "requirements.txt"], cwd=repo)
            if out.strip():
                try:
                    for vuln in json.loads(out):
                        for v in vuln.get("vulns", []):
                            findings.append({
                                "tool": "pip-audit",
                                "package": vuln.get("name"),
                                "severity": "HIGH",
                                "issue": v.get("id", "") + ": " + v.get("description", "")[:100],
                            })
                except json.JSONDecodeError:
                    pass

    if "package.json" in dep_files:
        if not _tool_available("npm"):
            unavailable.append("npm (install Node.js) — JS dep scan skipped")
        else:
            code, out, _ = run(["npm", "audit", "--json"], cwd=repo)
            if out.strip():
                try:
                    data = json.loads(out)
                    vulns = data.get("vulnerabilities", {})
                    for name, info in vulns.items():
                        sev = info.get("severity", "").upper()
                        if sev in ("CRITICAL", "HIGH"):
                            findings.append({
                                "tool": "npm-audit",
                                "package": name,
                                "severity": sev,
                                "issue": info.get("title", ""),
                            })
                except json.JSONDecodeError:
                    pass

    if "pom.xml" in dep_files or "build.gradle" in dep_files:
        if not _tool_available("mvn"):
            unavailable.append("mvn/owasp-dependency-check (install Maven) — Java dep scan skipped")
        else:
            code, out, _ = run(
                ["mvn", "-q", "org.owasp:dependency-check-maven:check",
                 "-DfailBuildOnCVSS=7", "-Dformat=JSON"],
                cwd=repo
            )
            report = Path(repo) / "target" / "dependency-check-report.json"
            if report.exists():
                try:
                    data = json.loads(report.read_text())
                    for dep in data.get("dependencies", []):
                        for vuln in dep.get("vulnerabilities", []):
                            if vuln.get("cvssv3", {}).get("baseScore", 0) >= 7:
                                findings.append({
                                    "tool": "owasp-dc",
                                    "package": dep.get("fileName", ""),
                                    "severity": "HIGH",
                                    "issue": vuln.get("name", "") + " CVSS:" + str(
                                        vuln.get("cvssv3", {}).get("baseScore")),
                                })
                except (json.JSONDecodeError, Exception):
                    pass

    for notice in unavailable:
        findings.append({"tool": "unavailable", "severity": "INFO", "issue": notice, "package": ""})

    return findings


def main():
    parser = argparse.ArgumentParser(description="Scan git diff for security issues")
    parser.add_argument("--branch", help="Story branch")
    parser.add_argument("--base", help="Base branch")
    parser.add_argument("--repo", required=True, help="Repo path")
    parser.add_argument("--staged", action="store_true", help="Scan staged files")
    args = parser.parse_args()

    if not args.staged and not (args.branch and args.base):
        print(json.dumps({"verdict": "ERROR", "summary": "--branch and --base required unless --staged"}))
        sys.exit(1)

    repo = str(Path(args.repo).resolve())
    changed = get_changed_files(args.branch, args.base, repo, args.staged)

    if not changed:
        print(json.dumps({
            "verdict": "PASS",
            "secrets": [], "sast": [], "deps": [],
            "changed_files": [],
            "summary": "No changed files"
        }))
        sys.exit(0)

    secrets = scan_secrets(changed, repo)
    sast = scan_sast(changed, repo)
    deps = scan_deps(changed, repo)

    # Determine verdict — INFO findings (unavailable tools) never affect verdict
    real_secrets = secrets
    real_sast = [s for s in sast if s.get("severity") != "INFO"]
    real_deps = [d for d in deps if d.get("severity") != "INFO"]
    info_notices = (
            [s["issue"] for s in sast if s.get("severity") == "INFO"] +
            [d["issue"] for d in deps if d.get("severity") == "INFO"]
    )

    if real_secrets or any(d.get("severity") == "CRITICAL" for d in real_deps):
        verdict = "BLOCKED"
    elif any(s.get("severity") == "HIGH" for s in real_sast) or \
            any(d.get("severity") == "HIGH" for d in real_deps):
        verdict = "WARNING"
    else:
        verdict = "PASS"

    total = len(real_secrets) + len(real_sast) + len(real_deps)
    summary = f"{verdict}: {len(changed)} files, {len(real_secrets)} secrets, {len(real_sast)} SAST, {len(real_deps)} dep issues"
    if info_notices:
        summary += f" | SKIPPED: {'; '.join(info_notices)}"

    print(json.dumps({
        "verdict": verdict,
        "secrets": secrets,
        "sast": sast,
        "deps": deps,
        "changed_files": changed,
        "summary": summary,
        "tools_unavailable": info_notices,
    }, indent=2))

    sys.exit(0 if verdict in ("PASS", "WARNING") else 1)


if __name__ == "__main__":
    main()
