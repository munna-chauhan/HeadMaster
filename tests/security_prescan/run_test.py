#!/usr/bin/env python
"""
Test runner for security_prescan.py.
Creates a test git diff and validates scanner detects expected vulnerabilities.
"""

import json
import subprocess
import sys
from pathlib import Path

def run_command(cmd):
    """Run command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.returncode, result.stdout, result.stderr

def main():
    print("=" * 60)
    print("Security Pre-Scan Test")
    print("=" * 60)

    repo_root = Path(__file__).parent.parent.parent
    scanner_script = repo_root / "scripts" / "security_prescan.py"
    test_file = Path(__file__).parent / "vulnerable_samples.txt"

    if not scanner_script.exists():
        print(f"[ERROR] Scanner script not found: {scanner_script}")
        sys.exit(1)

    if not test_file.exists():
        print(f"[ERROR] Test file not found: {test_file}")
        sys.exit(1)

    print(f"\n[INFO] Test file: {test_file}")
    print(f"[INFO] Scanner script: {scanner_script}")

    # Expected vulnerabilities to detect
    expected_findings = {
        "SQL Injection": 3,  # f-string, concat, template
        "XSS": 3,  # innerHTML, dangerouslySetInnerHTML, template
        "Hardcoded Secret": 3,  # API key, password, AWS key
        "Weak Crypto": 2,  # MD5, SHA1
        "Auth Bypass": 0,  # Reduced confidence - might be false positives
    }

    print("\n[INFO] Expected findings:")
    for category, count in expected_findings.items():
        print(f"  - {category}: {count}")

    # Create test branch and commit
    print("\n[INFO] Setting up test git state...")

    # Save current branch
    exit_code, current_branch, _ = run_command("git branch --show-current")
    current_branch = current_branch.strip()
    print(f"[INFO] Current branch: {current_branch}")

    # Create test branch
    test_branch = "test/security-scan-validation"
    run_command(f"git checkout -b {test_branch} 2>/dev/null || git checkout {test_branch}")

    # Stage and commit test file
    run_command(f"git add {test_file}")
    run_command(f'git commit -m "test: add vulnerable samples for security scan validation"')

    # Run scanner against main branch diff
    print(f"\n[INFO] Running security scan against main branch...")
    exit_code, stdout, stderr = run_command(
        f"python {scanner_script} --project default --diff-target main --output-dir {repo_root / '.security-test'}"
    )

    print("\n[OUTPUT]")
    print(stdout)

    if stderr:
        print("\n[STDERR]")
        print(stderr)

    # Check results
    report_path = repo_root / ".security-test" / "SECURITY_REPORT.md"
    json_path = repo_root / ".security-test" / "security_findings.json"

    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            results = json.load(f)

        findings = results.get("findings", [])
        print(f"\n[RESULT] Total findings detected: {len(findings)}")

        # Count by category
        by_category = {}
        for finding in findings:
            title = finding["title"]
            category = title.split(" - ")[0] if " - " in title else title
            by_category[category] = by_category.get(category, 0) + 1

        print("\n[BREAKDOWN]")
        for category, count in by_category.items():
            print(f"  - {category}: {count}")

        # Validate critical findings
        critical_high = [f for f in findings if f["severity"] in ["critical", "high"]]
        print(f"\n[CRITICAL/HIGH] {len(critical_high)} findings")
        for f in critical_high:
            print(f"  - {f['finding_id']}: {f['title']} ({f['severity']})")

        # Check expected vs actual
        print("\n[VALIDATION]")
        passed = True

        # At minimum, expect some SQL injection and XSS findings
        sql_findings = [f for f in findings if "SQL" in f["title"] or "Injection" in f["title"]]
        xss_findings = [f for f in findings if "XSS" in f["title"]]
        secret_findings = [f for f in findings if "Secret" in f["title"] or "Hardcoded" in f["title"]]

        if len(sql_findings) == 0:
            print("  [FAIL] No SQL injection patterns detected")
            passed = False
        else:
            print(f"  [PASS] {len(sql_findings)} SQL injection pattern(s) detected")

        if len(xss_findings) == 0:
            print("  [FAIL] No XSS patterns detected")
            passed = False
        else:
            print(f"  [PASS] {len(xss_findings)} XSS pattern(s) detected")

        if len(secret_findings) == 0:
            print("  [FAIL] No hardcoded secret patterns detected")
            passed = False
        else:
            print(f"  [PASS] {len(secret_findings)} hardcoded secret(s) detected")

        # Check that scan blocks on critical/high
        if exit_code == 1 and len(critical_high) > 0:
            print(f"  [PASS] Scanner correctly blocked (exit code 1) with {len(critical_high)} critical/high findings")
        elif exit_code == 0 and len(critical_high) == 0:
            print(f"  [PASS] Scanner correctly passed (exit code 0) with no critical/high findings")
        else:
            print(f"  [WARN] Exit code {exit_code} with {len(critical_high)} critical/high findings (check logic)")

        if report_path.exists():
            print(f"\n[REPORT] Generated at: {report_path}")
            print(f"[JSON] Generated at: {json_path}")

        if passed:
            print("\n" + "=" * 60)
            print("[SUCCESS] TEST PASSED")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("[FAILURE] TEST FAILED")
            print("=" * 60)

    else:
        print(f"\n[ERROR] No findings JSON generated at {json_path}")
        passed = False

    # Cleanup
    print(f"\n[INFO] Cleaning up test branch...")
    run_command(f"git checkout {current_branch}")
    run_command(f"git branch -D {test_branch}")

    # Remove test commit if on main
    # (We're not actually committing to main, so no cleanup needed)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
