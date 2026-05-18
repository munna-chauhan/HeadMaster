#!/bin/sh
""":"
for c in python3 py3 python py; do command -v "$c" >/dev/null 2>&1 && exec "$c" "$0" "$@"; done
for d in /c/Python* /c/Python*/Python* "/c/Program Files/Python"* "/c/Program Files/Python"*/Python* "/c/Program Files (x86)/Python"* "/c/Program Files (x86)/Python"*/Python* "$HOME/AppData/Local/Programs/Python/Python"* "$LOCALAPPDATA/Programs/Python/Python"*; do
  for n in python.exe python3.exe; do
    [ -x "$d/$n" ] && exec "$d/$n" "$0" "$@"
  done
done
echo "[HeadMaster] No python interpreter found (tried python3, py3, python, py, and common Windows install dirs)" >&2
exit 127
":"""
"""
Unit tests for scripts/parse_verdict.py

Run: sh scripts/tests/test_parse_verdict.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARSER = ROOT / "scripts" / "parse_verdict.py"
PYTHON = sys.executable

def run_parser(content: str, valid_verdicts: str) -> tuple[int, str, str]:
    """
    Run parse_verdict.py on test content.

    Returns:
        (exit_code, stdout, stderr)
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        f.flush()
        temp_path = f.name

    try:
        result = subprocess.run(
            [PYTHON, str(PARSER), temp_path, valid_verdicts],
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    finally:
        Path(temp_path).unlink()

def test_valid_verdict_new_format():
    """Test correct verdict extraction with new ## Verdict section format."""
    content = """# PRD Review

## Executive Summary
Some content here.

## Checklist Results
All items passed.

## Verdict
APPROVED
"""
    exit_code, stdout, stderr = run_parser(content, "APPROVED,CONDITIONAL,REJECTED")

    assert exit_code == 0, f"Expected exit 0, got {exit_code}. stderr: {stderr}"
    assert stdout == "APPROVED", f"Expected 'APPROVED', got '{stdout}'"
    print("OK test_valid_verdict_new_format")

def test_valid_verdict_conditional():
    """Test CONDITIONAL verdict extraction."""
    content = """# TDD Review

## Verdict
CONDITIONAL
"""
    exit_code, stdout, stderr = run_parser(content, "APPROVED,CONDITIONAL,REJECTED")

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    assert stdout == "CONDITIONAL", f"Expected 'CONDITIONAL', got '{stdout}'"
    print("OK test_valid_verdict_conditional")

def test_missing_verdict_section():
    """Test error when ## Verdict section missing."""
    content = """# PRD Review

## Executive Summary
Some content here.

## Checklist Results
All items passed.

No verdict section present.
"""
    exit_code, stdout, stderr = run_parser(content, "APPROVED,CONDITIONAL,REJECTED")

    assert exit_code == 1, f"Expected exit 1, got {exit_code}"
    assert "No '## Verdict' section found" in stderr, f"Unexpected stderr: {stderr}"
    print("OK test_missing_verdict_section")

def test_verdict_section_malformed():
    """Test error when verdict section exists but verdict not on next line."""
    content = """# PRD Review

## Verdict

The verdict is: APPROVED (missing proper format)
"""
    exit_code, stdout, stderr = run_parser(content, "APPROVED,CONDITIONAL,REJECTED")

    assert exit_code == 1, f"Expected exit 1, got {exit_code}"
    assert "No '## Verdict' section found" in stderr, f"Unexpected stderr: {stderr}"
    print("OK test_verdict_section_malformed")

def test_invalid_verdict_keyword():
    """Test error when verdict keyword not in valid list."""
    content = """# Code Review

## Verdict
MAYBE
"""
    exit_code, stdout, stderr = run_parser(content, "PASS,FINDINGS,BLOCKED")

    assert exit_code == 2, f"Expected exit 2, got {exit_code}"
    assert "Invalid verdict 'MAYBE'" in stderr, f"Unexpected stderr: {stderr}"
    print("OK test_invalid_verdict_keyword")

def test_verdict_in_prose_before_section():
    """Test warning when verdict keyword appears in prose before Verdict section."""
    content = """# Code Review

## History
Previous review PASSED without issues.
This iteration found new issues.

## Verdict
FINDINGS
"""
    exit_code, stdout, stderr = run_parser(content, "PASS,FINDINGS,BLOCKED")

    assert exit_code == 0, f"Expected exit 0 (should succeed), got {exit_code}"
    assert stdout == "FINDINGS", f"Expected 'FINDINGS', got '{stdout}'"
    # Should extract correct verdict despite "PASSED" in history
    print("OK test_verdict_in_prose_before_section")

def test_old_format_backwards_compat():
    """Test backwards compatibility with old 'Verdict:' format."""
    content = """# Code Review: STORY-123
Verdict: PASS | 2026-04-24T10:00:00Z
Diff: +50/-20 lines

## TDD Compliance
PASS
"""
    exit_code, stdout, stderr = run_parser(content, "PASS,FINDINGS,BLOCKED")

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    assert stdout == "PASS", f"Expected 'PASS', got '{stdout}'"
    assert "Old verdict format" in stderr, f"Expected backwards compat warning in stderr: {stderr}"
    print("OK test_old_format_backwards_compat")

def test_file_not_found():
    """Test error handling when file doesn't exist."""
    result = subprocess.run(
        [PYTHON, str(PARSER), "/nonexistent/file.md", "PASS"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 3, f"Expected exit 3, got {result.returncode}"
    assert "not found" in result.stderr, f"Unexpected stderr: {result.stderr}"
    print("OK test_file_not_found")

def test_case_insensitive():
    """Test that verdict matching is case-insensitive."""
    content = """# Review

## Verdict
approved
"""
    exit_code, stdout, stderr = run_parser(content, "APPROVED,CONDITIONAL,REJECTED")

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    assert stdout == "APPROVED", f"Expected 'APPROVED' (normalized), got '{stdout}'"
    print("OK test_case_insensitive")

def test_qa_report_verdicts():
    """Test QA-specific verdict extraction."""
    content = """# QA Report: STORY-456

## Verdict
APPROVED_PARTIAL
"""
    exit_code, stdout, stderr = run_parser(content, "APPROVED,APPROVED_PARTIAL,REJECTED-BUG")

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    assert stdout == "APPROVED_PARTIAL", f"Expected 'APPROVED_PARTIAL', got '{stdout}'"
    print("OK test_qa_report_verdicts")

def test_content_after_verdict():
    """Test warning when content appears after verdict."""
    content = """# Review

## Verdict
APPROVED

## Appendix
This should trigger a warning
"""
    exit_code, stdout, stderr = run_parser(content, "APPROVED,REJECTED")

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    assert stdout == "APPROVED", f"Expected 'APPROVED', got '{stdout}'"
    assert "WARNING" in stderr and "Content found after" in stderr, f"Expected warning in stderr: {stderr}"
    print("OK test_content_after_verdict")

if __name__ == "__main__":
    print("Running verdict parser unit tests...\n")

    try:
        test_valid_verdict_new_format()
        test_valid_verdict_conditional()
        test_missing_verdict_section()
        test_verdict_section_malformed()
        test_invalid_verdict_keyword()
        test_verdict_in_prose_before_section()
        test_old_format_backwards_compat()
        test_file_not_found()
        test_case_insensitive()
        test_qa_report_verdicts()
        test_content_after_verdict()

        print("\nOK All unit tests passed")
    except AssertionError as e:
        print(f"\nX Test failed: {e}")
        raise

    print("\nNote: These tests verify parser logic only.")
    print("Integration testing requires running actual skills with updated verdict format.")
