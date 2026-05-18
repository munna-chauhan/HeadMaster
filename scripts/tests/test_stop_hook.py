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
Unit tests for stop hook logic (does not test Claude Code enforcement).
Verifies return values of each stop hook under various conditions.

Run: sh scripts/tests/test_stop_hook.py

NOTE: Tests create artifacts in docs/features/default/test-stop-hook/ which are cleaned up automatically.
"""
import json
import subprocess
import shutil
import sys
from pathlib import Path

import pytest

PYTHON = sys.executable

# HeadMaster root
ROOT = Path(__file__).resolve().parents[2]
TEST_SLUG = "test-stop-hook"


def _active_project() -> str:
    """Resolve active project lazily. Tests skip if config.yml is absent."""
    import yaml
    import pytest
    cfg = ROOT / "config.yml"
    if not cfg.exists():
        pytest.skip("config.yml not present — copy config.yml.example to run hook tests")
    with open(cfg, encoding="utf-8") as f:
        return yaml.safe_load(f)["projects"]["active"]


TEST_PROJECT = None  # populated by autouse fixture below


@pytest.fixture(autouse=True)
def _resolve_active_project():
    global TEST_PROJECT
    TEST_PROJECT = _active_project()

def run_hook(hook_name, payload):
    """Execute a stop hook and return parsed JSON output."""
    result = subprocess.run(
        [PYTHON, f".claude/hooks/stop_checks/{hook_name}_stop.py", TEST_SLUG],
        cwd=ROOT,
        capture_output=True,
        text=True,
        input=json.dumps(payload),
    )

    if result.returncode != 0 and result.stderr:
        print(f"  Hook stderr: {result.stderr}")

    if not result.stdout:
        print(f"  Hook stdout empty. Return code: {result.returncode}")
        return {"ok": False, "reason": "Hook returned no output"}

    return json.loads(result.stdout)

def setup_test_feature():
    """Create test feature directory structure."""
    feature_dir = ROOT / f"docs/features/{TEST_PROJECT}/{TEST_SLUG}"
    if feature_dir.exists():
        shutil.rmtree(feature_dir)
    feature_dir.mkdir(parents=True, exist_ok=True)
    return feature_dir

def cleanup_test_feature():
    """Remove test feature directory."""
    feature_dir = ROOT / f"docs/features/{TEST_PROJECT}/{TEST_SLUG}"
    if feature_dir.exists():
        shutil.rmtree(feature_dir)

def test_plan_stop_approved():
    """Test plan_stop.py with approved PRD."""
    feature_dir = setup_test_feature()
    prd_dir = feature_dir / "planning"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd = prd_dir / "PRD.md"
    # Hook checks last 200 bytes, so put status at end
    content = "# PRD\n\nContent here.\n\n---\n\nPRD Status: APPROVED\n"
    prd.write_text(content, encoding="utf-8")

    # Verify file exists and has correct content
    assert prd.exists(), f"PRD file not created at {prd}"
    tail = prd.read_bytes()[-200:].decode("utf-8", errors="ignore")
    assert "PRD Status: APPROVED" in tail, f"APPROVED not in last 200 bytes: {repr(tail)}"

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("plan", payload)

    assert output["ok"] == True, f"Hook should pass with approved PRD, got: {output}"
    print("OK test_plan_stop_approved")

def test_plan_stop_not_approved():
    """Test plan_stop.py with unapproved PRD."""
    feature_dir = setup_test_feature()
    prd_dir = feature_dir / "planning"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd = prd_dir / "PRD.md"
    prd.write_text("# PRD\n\nContent here.\n\nPRD Status: DRAFT\n")

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("plan", payload)

    assert output["ok"] == False, f"Hook should block unapproved PRD, got: {output}"
    assert "not finalized" in output["reason"]
    print("OK test_plan_stop_not_approved")

def test_plan_stop_escape_hatch():
    """Test plan_stop.py with AskUserQuestion in last message."""
    feature_dir = setup_test_feature()
    prd_dir = feature_dir / "planning"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd = prd_dir / "PRD.md"
    prd.write_text("# PRD\n\nPRD Status: DRAFT\n")

    payload = {
        "stop_hook_active": False,
        "last_assistant_message": "Need input: <invoke name=\"AskUserQuestion\">"
    }
    output = run_hook("plan", payload)

    assert output["ok"] == True, f"Hook should pass when asking user, got: {output}"
    print("OK test_plan_stop_escape_hatch")

def test_design_stop_lite_tier():
    """Test design_stop.py with lite tier (IMPLEMENTATION_BRIEF.md)."""
    feature_dir = setup_test_feature()
    brief_dir = feature_dir / "design"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief = brief_dir / "IMPLEMENTATION_BRIEF.md"
    brief.write_text("""# Implementation Brief

## Section 1
Content

## Section 2
Content

## Section 3
Content

## Section 4
Content

## Section 5
Content
""")

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("design", payload)

    assert output["ok"] == True, f"Hook should pass with ≥5 sections, got: {output}"
    print("OK test_design_stop_lite_tier")

def test_design_stop_full_tier_approved():
    """Test design_stop.py with TDD review approved."""
    feature_dir = setup_test_feature()
    review_dir = feature_dir / "design"
    review_dir.mkdir(parents=True, exist_ok=True)
    review = review_dir / "TDD_REVIEW.md"
    review.write_text("# TDD Review\n\nVerdict: APPROVED\n\nAll checks passed.\n")

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("design", payload)

    assert output["ok"] == True, f"Hook should pass with APPROVED verdict, got: {output}"
    print("OK test_design_stop_full_tier_approved")

def test_design_stop_incomplete():
    """Test design_stop.py with incomplete design."""
    feature_dir = setup_test_feature()
    design_dir = feature_dir / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    # No IMPLEMENTATION_BRIEF.md or TDD_REVIEW.md

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("design", payload)

    assert output["ok"] == False, f"Hook should block incomplete design, got: {output}"
    assert "not finalized" in output["reason"]
    print("OK test_design_stop_incomplete")

def test_breakdown_stop_complete():
    """Test breakdown_stop.py with JIRA_BREAKDOWN.md containing Push Status."""
    feature_dir = setup_test_feature()
    breakdown_dir = feature_dir / "breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    breakdown = breakdown_dir / "JIRA_BREAKDOWN.md"
    breakdown.write_text("""# JIRA Breakdown

| Story | Key | Status |
|-------|-----|--------|
| S1    | KEY-1 | NEW  |

Push Status: PUSHED
""")

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("breakdown", payload)

    assert output["ok"] == True, f"Hook should pass with Push Status present, got: {output}"
    print("OK test_breakdown_stop_complete")

def test_breakdown_stop_incomplete():
    """Test breakdown_stop.py with missing breakdown."""
    feature_dir = setup_test_feature()
    # No JIRA_BREAKDOWN.md created

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("breakdown", payload)

    assert output["ok"] == False, f"Hook should block missing breakdown, got: {output}"
    assert "missing or incomplete" in output["reason"]
    print("OK test_breakdown_stop_incomplete")

def test_execute_stop_active_work():
    """Test execute_stop.py with stories in progress."""
    feature_dir = setup_test_feature()
    breakdown_dir = feature_dir / "breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    breakdown = breakdown_dir / "JIRA_BREAKDOWN.md"
    breakdown.write_text("""# JIRA Breakdown

| Story | Status |
|-------|--------|
| S1    | IN PROGRESS |
| S2    | NEW |
""")

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("execute", payload)

    assert output["ok"] == True, f"Hook should pass with active work (resumable), got: {output}"
    print("OK test_execute_stop_active_work")

def test_execute_stop_incomplete():
    """Test execute_stop.py with NEW stories remaining."""
    feature_dir = setup_test_feature()
    breakdown_dir = feature_dir / "breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    breakdown = breakdown_dir / "JIRA_BREAKDOWN.md"
    breakdown.write_text("""# JIRA Breakdown

| Story | Status |
|-------|--------|
| S1    | COMPLETE |
| S2    | NEW |
""")

    # No system-review.md

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("execute", payload)

    assert output["ok"] == False, f"Hook should block NEW stories without system review, got: {output}"
    assert "remain NEW" in output["reason"]
    print("OK test_execute_stop_incomplete")

def test_execute_stop_complete():
    """Test execute_stop.py with all stories done + system review."""
    feature_dir = setup_test_feature()
    breakdown_dir = feature_dir / "breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    breakdown = breakdown_dir / "JIRA_BREAKDOWN.md"
    breakdown.write_text("""# JIRA Breakdown

| Story | Status |
|-------|--------|
| S1    | COMPLETE |
| S2    | COMPLETE |
""")

    review_dir = feature_dir / "retrospective"
    review_dir.mkdir(parents=True, exist_ok=True)
    review = review_dir / "system-review.md"
    review.write_text("# System Review\n\nAll stories validated.\n")

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("execute", payload)

    assert output["ok"] == True, f"Hook should pass when execution complete, got: {output}"
    print("OK test_execute_stop_complete")

def test_stop_hook_loop_prevention():
    """Test that stop_hook_active flag prevents infinite loops."""
    feature_dir = setup_test_feature()
    # No PRD (would normally fail)

    payload = {"stop_hook_active": True, "last_assistant_message": ""}
    output = run_hook("plan", payload)

    assert output["ok"] == True, f"Hook should pass immediately when stop_hook_active=True, got: {output}"
    print("OK test_stop_hook_loop_prevention")

def test_verdict_found_in_last_500_bytes_not_first():
    """Test design_stop.py finds verdict in last 500 bytes even with verbose preamble."""
    feature_dir = setup_test_feature()
    review_dir = feature_dir / "design"
    review_dir.mkdir(parents=True, exist_ok=True)
    review = review_dir / "TDD_REVIEW.md"

    # Create verbose preamble that pushes verdict past first 500 bytes
    preamble = "# TDD Review\n\n" + "This is verbose preamble text. " * 50 + "\n\n"
    verdict = "\n\n## Verdict\n\nAPPROVED\n\nAll checks passed.\n"

    content = preamble + verdict
    review.write_text(content)

    # Verify verdict is NOT in first 500 bytes
    first_500 = content[:500]
    assert "APPROVED" not in first_500, "Test setup incorrect: verdict should not be in first 500 bytes"

    # Verify verdict IS in last 500 bytes
    last_500 = content[-500:]
    assert "APPROVED" in last_500, "Test setup incorrect: verdict should be in last 500 bytes"

    payload = {"stop_hook_active": False, "last_assistant_message": ""}
    output = run_hook("design", payload)

    assert output["ok"] == True, f"Hook should find APPROVED in last 500 bytes, got: {output}"
    print("OK test_verdict_found_in_last_500_bytes_not_first")

if __name__ == "__main__":
    print("Running stop hook unit tests...\n")

    try:
        # Plan hook tests
        test_plan_stop_approved()
        cleanup_test_feature()

        test_plan_stop_not_approved()
        cleanup_test_feature()

        test_plan_stop_escape_hatch()
        cleanup_test_feature()

        # Design hook tests
        test_design_stop_lite_tier()
        cleanup_test_feature()

        test_design_stop_full_tier_approved()
        cleanup_test_feature()

        test_design_stop_incomplete()
        cleanup_test_feature()

        # Breakdown hook tests
        test_breakdown_stop_complete()
        cleanup_test_feature()

        test_breakdown_stop_incomplete()
        cleanup_test_feature()

        # Execute hook tests
        test_execute_stop_active_work()
        cleanup_test_feature()

        test_execute_stop_incomplete()
        cleanup_test_feature()

        test_execute_stop_complete()
        cleanup_test_feature()

        # Common behavior tests
        test_stop_hook_loop_prevention()
        cleanup_test_feature()

        test_verdict_found_in_last_500_bytes_not_first()
        cleanup_test_feature()

        print("\nOK All unit tests passed")
        print("Test artifacts cleaned up.")
    except Exception as e:
        cleanup_test_feature()
        print(f"\nX Test failed: {e}")
        raise

    print("\nNote: These tests verify hook logic only, NOT Claude Code enforcement.")
    print("See .claude/review/stop-hook-verification.md for manual verification procedure.")
