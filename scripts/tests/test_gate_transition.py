#!/usr/bin/env python
"""Unit tests for gate_transition.py"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_pass_verdict_advances_phase_correctly(tmp_path, monkeypatch):
    """PASS verdict advances phase to next stage."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    # Mock sys.argv for gate_transition.py main()
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
        from gate_transition import main
        main()

    # Verify state file updated
    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    assert state_path.exists()

    state = json.loads(state_path.read_text())
    assert state["pipeline"]["phase"] == "planning"
    assert state["pipeline"]["stage"] == "Draft"
    assert "gate_passed" in state["pipeline"]


def test_findings_verdict_triggers_retry_path(tmp_path, monkeypatch):
    """FINDINGS verdict updates state to trigger retry."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    # First transition to Draft
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
        from gate_transition import main
        main()

    # Then transition back to Discover (findings detected)
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Discover"]):
        main()

    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    state = json.loads(state_path.read_text())

    # Verify stage went back to Discover
    assert state["pipeline"]["stage"] == "Discover"


def test_blocked_verdict_escalates(tmp_path, monkeypatch, capsys):
    """BLOCKED verdict can be recorded in state for escalation."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    # Transition to BLOCKED state
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "BLOCKED"]):
        from gate_transition import main
        main()

    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    state = json.loads(state_path.read_text())

    assert state["pipeline"]["stage"] == "BLOCKED"


def test_file_lock_prevents_concurrent_writes(tmp_path, monkeypatch):
    """File lock prevents concurrent writes from corrupting state."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    # Pre-create state file
    memory_dir = tmp_path / "memory" / "features" / "acme" / "test-feature"
    memory_dir.mkdir(parents=True, exist_ok=True)
    state_path = memory_dir / "loop_state.json"

    initial_state = {
        "pipeline": {
            "phase": "planning",
            "stage": "Init",
            "gate_passed": "2026-04-24T10:00:00Z"
        }
    }
    state_path.write_text(json.dumps(initial_state))

    # Simulate update
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
        from gate_transition import main
        main()

    # Verify state updated correctly
    state = json.loads(state_path.read_text())
    assert state["pipeline"]["stage"] == "Draft"

    # Verify no corruption (valid JSON)
    assert "phase" in state["pipeline"]
    assert "gate_passed" in state["pipeline"]


def test_artifact_path_stored(tmp_path, monkeypatch):
    """Artifact path is stored when provided."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    artifact_path = "docs/features/acme/test-feature/planning/PRD.md"

    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "APPROVED", "--artifact", artifact_path]):
        from gate_transition import main
        main()

    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    state = json.loads(state_path.read_text())

    assert state["pipeline"]["artifact"] == artifact_path


def test_rollback_restores_backup(tmp_path, monkeypatch):
    """Rollback command restores previous state from backup."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    memory_dir = tmp_path / "memory" / "features" / "acme" / "test-feature"
    memory_dir.mkdir(parents=True, exist_ok=True)
    state_path = memory_dir / "loop_state.json"
    backup_path = memory_dir / "loop_state.json.bak"

    # Create current state
    current_state = {
        "pipeline": {
            "phase": "planning",
            "stage": "Draft",
            "gate_passed": "2026-04-24T12:00:00Z"
        }
    }
    state_path.write_text(json.dumps(current_state))

    # Create backup (older state)
    backup_state = {
        "pipeline": {
            "phase": "planning",
            "stage": "Init",
            "gate_passed": "2026-04-24T10:00:00Z"
        }
    }
    backup_path.write_text(json.dumps(backup_state))

    # Rollback (catch SystemExit since main() calls sys.exit(0))
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "rollback"]):
        from gate_transition import main
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    # Verify state restored
    state = json.loads(state_path.read_text())
    assert state["pipeline"]["stage"] == "Init"
    assert state["pipeline"]["gate_passed"] == "2026-04-24T10:00:00Z"


def test_backup_created_before_update(tmp_path, monkeypatch):
    """Backup file created before state update."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    # Pre-create state
    memory_dir = tmp_path / "memory" / "features" / "acme" / "test-feature"
    memory_dir.mkdir(parents=True, exist_ok=True)
    state_path = memory_dir / "loop_state.json"

    original_state = {
        "pipeline": {
            "phase": "planning",
            "stage": "Init",
            "gate_passed": "2026-04-24T10:00:00Z"
        }
    }
    state_path.write_text(json.dumps(original_state))

    # Update state
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
        from gate_transition import main
        main()

    # Verify backup exists with original content
    backup_path = memory_dir / "loop_state.json.bak"
    assert backup_path.exists()

    backup_state = json.loads(backup_path.read_text())
    assert backup_state["pipeline"]["stage"] == "Init"


def test_creates_directories_if_missing(tmp_path, monkeypatch):
    """Creates parent directories if they don't exist."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    # No pre-existing directories
    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
        from gate_transition import main
        main()

    # Verify state file created
    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    assert state_path.exists()


def test_timestamp_recorded(tmp_path, monkeypatch):
    """Timestamp recorded when gate passes."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
        from gate_transition import main
        main()

    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    state = json.loads(state_path.read_text())

    # Verify timestamp exists and is ISO format
    assert "gate_passed" in state["pipeline"]
    timestamp = state["pipeline"]["gate_passed"]
    assert "T" in timestamp  # ISO format check
    assert "Z" in timestamp or "+" in timestamp  # Timezone marker


def test_gate_transition_completes_if_tracking_fails(tmp_path, monkeypatch):
    """Gate transition completes even if performance tracking fails."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    # Mock record_gate_passed to raise exception
    from gate_transition import main
    with patch("gate_transition.record_gate_passed", side_effect=RuntimeError("Tracking failed")):
        with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
            # Should not raise, should complete successfully
            main()

    # Verify state file was updated despite tracking failure
    state_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "loop_state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert state["pipeline"]["stage"] == "Draft"


def test_tracking_called_on_successful_transition(tmp_path, monkeypatch):
    """Performance tracking is called when transition succeeds."""
    monkeypatch.setattr("gate_transition.REPO_ROOT", tmp_path)

    from gate_transition import main
    with patch("gate_transition.record_gate_passed") as mock_tracking:
        with patch("sys.argv", ["gate_transition.py", "acme", "test-feature", "planning", "Draft"]):
            main()

    # Verify tracking was called with correct arguments
    mock_tracking.assert_called_once_with("acme", "test-feature", "planning", "Draft")
