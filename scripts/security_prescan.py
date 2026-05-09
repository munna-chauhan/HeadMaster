#!/usr/bin/env python
"""
Security pre-scan for HeadMaster pipeline.

Static security analysis on git diff before PR creation.
Checks: SQL injection, XSS, auth bypass, secrets, dependency vulnerabilities.
Maps findings to OWASP Top 10.

Usage:
    python scripts/security_prescan.py --project default --feature my-feature --diff-target main
    python scripts/security_prescan.py --diff-target main  # Uses active project from config
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
import datetime

try:
    import yaml
except ImportError:
    print("[ERROR] Missing dependency: pip install pyyaml")
    sys.exit(1)


def safe_run(cmd: List[str], cwd: Optional[str] = None) -> tuple[int, str, str]:
    """Run subprocess safely, return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
            encoding='utf-8',
            errors='ignore'
        )
        return result.returncode, result.stdout, result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, "", str(e)


def load_config() -> dict:
    """Load HeadMaster config.yml."""
    config_path = Path(__file__).parent.parent / "config.yml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


@dataclass
class Finding:
    finding_id: str
    severity: str  # critical, high, medium, low
    owasp_category: str  # A01-A10
    title: str
    file: str
    line: Optional[int]
    issue: str
    fix: str
    confidence: int  # 0-100


# OWASP Top 10 2021 mapping
OWASP_MAP = {
    "A01": "Broken Access Control",
    "A02": "Cryptographic Failures",
    "A03": "Injection",
    "A04": "Insecure Design",
    "A05": "Security Misconfiguration",
    "A06": "Vulnerable and Outdated Components",
    "A07": "Identification and Authentication Failures",
    "A08": "Software and Data Integrity Failures",
    "A09": "Security Logging and Monitoring Failures",
    "A10": "Server-Side Request Forgery",
}


# Security patterns to detect
SECURITY_PATTERNS = [
    # SQL Injection (A03)
    {
        "name": "SQL Injection - Python f-string",
        "regex": r"execute\([f'\"].*\{.*\}.*[f'\"]\)",
        "owasp": "A03",
        "severity": "critical",
        "confidence": 90,
        "fix": "Use parameterized queries with placeholders: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    },
    {
        "name": "SQL Injection - Template literal",
        "regex": r"query\(`.*\$\{.*\}.*`\)",
        "owasp": "A03",
        "severity": "critical",
        "confidence": 90,
        "fix": "Use parameterized queries: db.query('SELECT * FROM users WHERE name = $1', [name])",
    },
    {
        "name": "SQL Injection - String concatenation",
        "regex": r"(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE).*[\+].*['\"]",
        "owasp": "A03",
        "severity": "high",
        "confidence": 75,
        "fix": "Use parameterized queries instead of string concatenation",
    },

    # XSS (A03)
    {
        "name": "XSS - Direct innerHTML assignment",
        "regex": r"\.innerHTML\s*=\s*(?!['\"]\s*$)",
        "owasp": "A03",
        "severity": "high",
        "confidence": 85,
        "fix": "Use textContent for plain text or sanitize HTML with DOMPurify before assignment",
    },
    {
        "name": "XSS - React dangerouslySetInnerHTML",
        "regex": r"dangerouslySetInnerHTML",
        "owasp": "A03",
        "severity": "high",
        "confidence": 80,
        "fix": "Sanitize HTML with DOMPurify or use React's safe rendering",
    },
    {
        "name": "XSS - Template literal in HTML",
        "regex": r"<[^>]*\$\{[^}]+\}[^>]*>",
        "owasp": "A03",
        "severity": "high",
        "confidence": 70,
        "fix": "Escape user input or use framework's safe rendering (e.g., React JSX)",
    },

    # Auth Bypass (A07)
    {
        "name": "Auth Bypass - Flask route without decorator",
        "regex": r"@app\.route\(['\"].*['\"],\s*methods=\[.*['\"]POST['\"].*\]\)",
        "owasp": "A07",
        "severity": "high",
        "confidence": 60,
        "fix": "Add @login_required or @auth_required decorator to protected routes",
    },
    {
        "name": "Auth Bypass - Next.js API without auth",
        "regex": r"export\s+async\s+function\s+(POST|PUT|DELETE|PATCH)\s*\(",
        "owasp": "A07",
        "severity": "medium",
        "confidence": 50,
        "fix": "Add authentication check at the start of API route handler",
    },

    # Secrets (A05)
    {
        "name": "Hardcoded Secret - Generic",
        "regex": r"(?i)(password|secret|api[_-]?key)\s*[=:]\s*['\"][^'\"]{8,}['\"]",
        "owasp": "A05",
        "severity": "critical",
        "confidence": 85,
        "fix": "Move secrets to environment variables or secure vault",
    },
    {
        "name": "Hardcoded Secret - AWS Key",
        "regex": r"AKIA[0-9A-Z]{16}",
        "owasp": "A05",
        "severity": "critical",
        "confidence": 95,
        "fix": "Remove hardcoded AWS key, rotate compromised key, use IAM roles or environment variables",
    },

    # Insecure Crypto (A02)
    {
        "name": "Weak Crypto - MD5",
        "regex": r"\b(md5|MD5)\s*\(",
        "owasp": "A02",
        "severity": "medium",
        "confidence": 70,
        "fix": "Use SHA-256 or SHA-3 for hashing, bcrypt/argon2 for passwords",
    },
    {
        "name": "Weak Crypto - SHA1",
        "regex": r"\b(sha1|SHA1)\s*\(",
        "owasp": "A02",
        "severity": "medium",
        "confidence": 70,
        "fix": "Use SHA-256 or SHA-3 instead of deprecated SHA-1",
    },
]


# Allowlist patterns to reduce false positives
ALLOWLIST_PATTERNS = [
    r"test[_\-]?password",
    r"example",
    r"placeholder",
    r"changeit",
    r"password123",
    r"dummy",
    r"mock",
    r"fake",
    r"# TODO",
    r"# FIXME",
]


def is_allowlisted(line: str) -> bool:
    """Check if line contains allowlisted test/example content."""
    lower = line.lower()
    return any(re.search(pattern, lower, re.IGNORECASE) for pattern in ALLOWLIST_PATTERNS)


def get_git_diff(target_branch: str, repo_path: str = ".") -> List[tuple[str, str]]:
    """Get git diff content. Returns list of (file_path, diff_content) tuples."""
    exit_code, stdout, stderr = safe_run(
        ["git", "diff", f"{target_branch}...HEAD", "--unified=3"],
        cwd=repo_path
    )

    if exit_code != 0 or not stdout:
        if stderr:
            print(f"[ERROR] git diff failed: {stderr}")
        return []

    # Parse diff to extract file changes
    files_content = {}
    current_file = None
    current_content = []

    for line in stdout.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files_content[current_file] = "\n".join(current_content)
            # Extract file path
            parts = line.split(" b/")
            if len(parts) == 2:
                current_file = parts[1]
                current_content = []
        elif current_file:
            current_content.append(line)

    if current_file:
        files_content[current_file] = "\n".join(current_content)

    return [(f, c) for f, c in files_content.items()]


def scan_diff_for_patterns(diff_files: List[tuple[str, str]]) -> List[Finding]:
    """Scan git diff for security patterns."""
    findings = []
    finding_counter = 1

    for file_path, diff_content in diff_files:
        # Only scan added lines (starting with +)
        added_lines = []
        line_num = 0

        for line in diff_content.splitlines():
            if line.startswith("@@"):
                # Extract line number from diff header
                match = re.search(r"\+(\d+)", line)
                if match:
                    line_num = int(match.group(1))
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append((line_num, line[1:]))  # Remove + prefix
                line_num += 1
            elif not line.startswith("-"):
                line_num += 1

        # Scan added lines against patterns
        for line_num, line in added_lines:
            if is_allowlisted(line):
                continue

            for pattern in SECURITY_PATTERNS:
                if re.search(pattern["regex"], line):
                    findings.append(Finding(
                        finding_id=f"SEC-{finding_counter:03d}",
                        severity=pattern["severity"],
                        owasp_category=pattern["owasp"],
                        title=pattern["name"],
                        file=file_path,
                        line=line_num,
                        issue=f"Pattern detected: {line.strip()[:80]}",
                        fix=pattern["fix"],
                        confidence=pattern["confidence"],
                    ))
                    finding_counter += 1

    return findings


def run_dependency_audit(project_root: str) -> List[Finding]:
    """Run npm audit and pip check for dependency vulnerabilities."""
    findings = []
    finding_counter = 1000  # Offset to avoid collision with pattern findings

    # Check for package.json (npm)
    package_json = Path(project_root) / "package.json"
    if package_json.exists():
        exit_code, stdout, stderr = safe_run(["npm", "audit", "--json"], cwd=project_root)
        if exit_code != 0 and stdout:
            try:
                audit_data = json.loads(stdout)
                vulnerabilities = audit_data.get("vulnerabilities", {})

                for pkg_name, vuln_info in vulnerabilities.items():
                    severity = vuln_info.get("severity", "low")
                    if severity in ["critical", "high"]:
                        findings.append(Finding(
                            finding_id=f"DEP-{finding_counter:03d}",
                            severity=severity,
                            owasp_category="A06",
                            title=f"Vulnerable Dependency - {pkg_name}",
                            file="package.json",
                            line=None,
                            issue=f"Package {pkg_name} has {severity} vulnerability",
                            fix=f"Run 'npm audit fix' or update {pkg_name} to a safe version",
                            confidence=95,
                        ))
                        finding_counter += 1
            except json.JSONDecodeError:
                pass

    # Check for requirements.txt or pyproject.toml (Python)
    requirements = Path(project_root) / "requirements.txt"
    pyproject = Path(project_root) / "pyproject.toml"

    if requirements.exists() or pyproject.exists():
        # pip check doesn't give structured output, so we'll skip detailed parsing
        exit_code, stdout, stderr = safe_run(["pip", "check"], cwd=project_root)
        if exit_code != 0 and stdout:
            findings.append(Finding(
                finding_id=f"DEP-{finding_counter:03d}",
                severity="medium",
                owasp_category="A06",
                title="Python Dependency Issues",
                file="requirements.txt",
                line=None,
                issue=stdout.strip()[:200],
                fix="Review pip check output and update conflicting packages",
                confidence=70,
            ))

    return findings


def generate_report(findings: List[Finding], output_dir: Path) -> tuple[str, str]:
    """Generate JSON and Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    json_path = output_dir / "security_findings.json"
    findings_dict = [asdict(f) for f in findings]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_date": datetime.datetime.now().isoformat(),
            "total_findings": len(findings),
            "findings": findings_dict,
        }, f, indent=2)

    # Markdown report
    md_path = output_dir / "SECURITY_REPORT.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Security Pre-Scan Report\n\n")
        f.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Findings:** {len(findings)}\n\n")

        # Summary by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for finding in findings:
            by_severity[finding.severity].append(finding)

        f.write("## Summary\n\n")
        f.write(f"- 🔴 Critical: {len(by_severity['critical'])}\n")
        f.write(f"- 🟠 High: {len(by_severity['high'])}\n")
        f.write(f"- 🟡 Medium: {len(by_severity['medium'])}\n")
        f.write(f"- ⚪ Low: {len(by_severity['low'])}\n\n")

        # Detailed findings
        f.write("## Findings\n\n")
        for severity in ["critical", "high", "medium", "low"]:
            if by_severity[severity]:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}[severity]
                f.write(f"### {icon} {severity.upper()}\n\n")

                for finding in by_severity[severity]:
                    f.write(f"#### {finding.finding_id} - {finding.title}\n\n")
                    f.write(f"**OWASP:** {finding.owasp_category} - {OWASP_MAP.get(finding.owasp_category, 'Unknown')}\n\n")
                    f.write(f"**File:** `{finding.file}`")
                    if finding.line:
                        f.write(f" (line {finding.line})")
                    f.write("\n\n")
                    f.write(f"**Issue:** {finding.issue}\n\n")
                    f.write(f"**Fix:** {finding.fix}\n\n")
                    f.write(f"**Confidence:** {finding.confidence}%\n\n")
                    f.write("---\n\n")

    return str(json_path), str(md_path)


def main():
    parser = argparse.ArgumentParser(description="Security pre-scan for HeadMaster")
    parser.add_argument("--project", help="Project name (defaults to active project in config)")
    parser.add_argument("--feature", help="Feature slug (optional, for logging)")
    parser.add_argument("--diff-target", required=True, help="Git branch to diff against (e.g., main)")
    parser.add_argument("--output-dir", help="Output directory for reports (default: .security)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Minimal output: verdict + counts only (saves tokens when called from agents)")

    args = parser.parse_args()

    # Load config
    config = load_config()

    # Determine project
    project = args.project
    if not project:
        project = config.get("projects", {}).get("active", "default")

    project_config = config.get("projects", {}).get(project, {})
    project_root = project_config.get("root", ".")
    project_path = Path(project_root).resolve()

    if not project_path.exists():
        print(f"[ERROR] Project root does not exist: {project_path}")
        sys.exit(1)

    # Output directory
    output_dir = Path(args.output_dir) if args.output_dir else project_path / ".security"

    quiet = args.quiet

    if not quiet:
        print(f"[INFO] Security pre-scan: {project} vs {args.diff_target}", file=sys.stderr)

    # Get git diff
    diff_files = get_git_diff(args.diff_target, str(project_path))
    if not diff_files:
        print("PASS: no changes to scan")
        sys.exit(0)

    if not quiet:
        print(f"[INFO] Scanning {len(diff_files)} files", file=sys.stderr)

    # Scan for patterns
    findings = scan_diff_for_patterns(diff_files)

    # Run dependency audit
    dep_findings = run_dependency_audit(str(project_path))
    findings.extend(dep_findings)

    # Generate reports (always write to disk for human review)
    if findings:
        json_path, md_path = generate_report(findings, output_dir)

        # Count by severity
        counts = {s: 0 for s in ["critical", "high", "medium", "low"]}
        for f in findings:
            counts[f.severity] += 1
        critical_high = counts["critical"] + counts["high"]

        if quiet:
            # Minimal output: verdict + counts only
            verdict = "BLOCKED" if critical_high else "WARNING"
            print(f"{verdict}: {len(findings)} findings (critical={counts['critical']} high={counts['high']} medium={counts['medium']} low={counts['low']})")
            if critical_high:
                print(f"Report: {md_path}")
        else:
            print(f"\n[REPORT] {json_path}", file=sys.stderr)
            print(f"[REPORT] {md_path}", file=sys.stderr)
            print(f"[RESULT] {len(findings)} findings: critical={counts['critical']} high={counts['high']} medium={counts['medium']} low={counts['low']}")

            if critical_high:
                print(f"[BLOCKED] {critical_high} critical/high findings block PR")

        sys.exit(1 if critical_high else 0)
    else:
        print("PASS: no findings")
        sys.exit(0)


if __name__ == "__main__":
    main()
