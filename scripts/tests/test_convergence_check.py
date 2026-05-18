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
"""Unit tests for convergence_check.py"""

import json
import pytest
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from convergence_check import check_convergence, _blocker_id


def test_converged_when_below_max_loops(tmp_path, monkeypatch):
    """Returns CONTINUE when loop count below max."""
    monkeypatch.setattr("convergence_check.REPO_ROOT", tmp_path)

    findings = [{"section": "Requirements", "issue": "Missing acceptance criteria"}]
    result = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=3)

    assert result["verdict"] == "continue"
    assert result["iteration"] == 1
    assert "converging" in result["reason"].lower()


def test_escalate_when_max_loops_exceeded(tmp_path, monkeypatch):
    """Returns ESCALATE when loop count hits max."""
    monkeypatch.setattr("convergence_check.REPO_ROOT", tmp_path)

    # Pre-populate state with 3 iterations
    memory_dir = tmp_path / "memory" / "features" / "acme" / "test-feature"
    memory_dir.mkdir(parents=True, exist_ok=True)
    state_path = memory_dir / "loop_state.json"

    state = {
        "planning": {
            "iteration": 3,
            "blocker_history": [],
            "stage_visits": {"Discover": 3, "Review": 3}
        }
    }
    state_path.write_text(json.dumps(state))

    findings = [{"section": "Requirements", "issue": "Still missing criteria"}]
    result = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=3)

    assert result["verdict"] == "escalate"
    assert result["iteration"] == 4
    # Check triggers stage visit limit before max loops check
    assert ("max" in result["reason"].lower() or "visited" in result["reason"].lower())


def test_reads_max_loops_from_config_not_hardcode(tmp_path, monkeypatch):
    """Check uses max_loops parameter from config.yml, not hardcoded value."""
    monkeypatch.setattr("convergence_check.REPO_ROOT", tmp_path)

    # Verify that ConfigResolver is used to read max_loops from config.yml
    # The main() function should read from config.get('pipeline.max_loops', default=3)
    # This test verifies that check_convergence respects the max_loops parameter
    # (in real usage, main() passes this value from config)

    findings = [{"section": "Requirements", "issue": "Missing criteria"}]

    # With max_loops=2, should escalate on 3rd iteration (not default 3)
    result1 = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=2)
    result2 = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=2)
    result3 = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=2)

    assert result1["verdict"] == "continue"
    assert result2["verdict"] == "continue"
    assert result3["verdict"] == "escalate", "Should escalate on 3rd iteration when max_loops=2"
    assert result3["iteration"] == 3


def test_uses_correct_project_scoped_path(tmp_path, monkeypatch):
    """Check uses memory/features/{project}/{slug}/ path."""
    monkeypatch.setattr("convergence_check.REPO_ROOT", tmp_path)

    findings = [{"section": "Requirements", "issue": "Missing criteria"}]

    # Run for acme project
    check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=3)

    # Verify correct path exists
    project_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    assert project_path.exists(), f"Expected path not found: {project_path}"

    # Verify wrong path does NOT exist
    wrong_path = tmp_path / "memory" / "features" / "test-feature" / "loop_state.json"
    assert not wrong_path.exists(), f"Wrong path should not exist: {wrong_path}"


def test_handles_missing_loop_state_gracefully(tmp_path, monkeypatch):
    """Check handles missing loop_state.json without crash."""
    monkeypatch.setattr("convergence_check.REPO_ROOT", tmp_path)

    # No pre-existing state file
    findings = [{"section": "Requirements", "issue": "Missing criteria"}]
    result = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=3)

    # Should create state and return iteration 1
    assert result["verdict"] == "continue"
    assert result["iteration"] == 1

    # Verify file was created
    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    assert state_path.exists()


def test_detects_recurrent_blocker(tmp_path, monkeypatch):
    """Check escalates when previously resolved blocker returns."""
    monkeypatch.setattr("convergence_check.REPO_ROOT", tmp_path)

    findings1 = [{"section": "Requirements", "issue": "Missing acceptance criteria"}]
    findings2 = []  # Blocker resolved
    findings3 = [{"section": "Requirements", "issue": "Missing acceptance criteria"}]  # Same blocker back

    result1 = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings1, max_loops=3)
    assert result1["verdict"] == "continue"

    result2 = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings2, max_loops=3)
    assert result2["verdict"] == "continue"

    result3 = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings3, max_loops=3)
    assert result3["verdict"] == "escalate"
    assert "recurrent" in result3["reason"].lower()


def test_blocker_id_deduplication():
    """Verify blocker ID normalizes similar issues."""
    finding1 = {"section": "Requirements", "issue": "The user needs to provide missing acceptance criteria"}
    finding2 = {"section": "Requirements", "issue": "User needs provide missing acceptance criteria"}

    id1 = _blocker_id(finding1)
    id2 = _blocker_id(finding2)

    # Should be same ID (stop words removed, normalized)
    assert id1 == id2


def test_stage_visit_limit(tmp_path, monkeypatch):
    """Check escalates when stage visited too many times."""
    monkeypatch.setattr("convergence_check.REPO_ROOT", tmp_path)

    findings = [{"section": "Requirements", "issue": "Missing criteria"}]

    # Visit Discover stage 4 times (max is 3)
    for i in range(4):
        result = check_convergence("acme", "test-feature", "planning", "DISCOVERY_GAP", findings, max_loops=3)
        if i < 3:
            assert result["verdict"] == "continue"
        else:
            assert result["verdict"] == "escalate"
            assert "visited" in result["reason"].lower()
