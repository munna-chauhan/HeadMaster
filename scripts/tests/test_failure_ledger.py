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
"""Unit tests for failure_ledger.py"""

import json
import pytest
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from failure_ledger import _ledger_path, _load_ledger, _save_ledger, cmd_append, cmd_load, cmd_check


def test_append_adds_entry_correctly(tmp_path, monkeypatch, capsys):
    """Append adds record to ledger with correct structure."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    record_json = json.dumps({
        "approach": "Added null check",
        "error_type": "test_failure",
        "error_summary": "NPE at line 42",
        "files_touched": ["UserService.java"],
        "hypothesis": "Mock not configured"
    })

    cmd_append("acme", "test-feature", "ACME-123", record_json)

    # Verify ledger file exists
    ledger_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "failure-ledger-ACME-123.json"
    assert ledger_path.exists()

    # Verify content
    records = json.loads(ledger_path.read_text())
    assert len(records) == 1
    assert records[0]["approach"] == "Added null check"
    assert records[0]["story_key"] == "ACME-123"
    assert records[0]["attempt"] == 1
    assert "timestamp" in records[0]
    assert records[0]["excluded_approaches"] == ["Added null check"]


def test_read_returns_all_entries_for_correct_project(tmp_path, monkeypatch, capsys):
    """Read returns all entries for correct project/slug."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    # Add two records
    record1 = json.dumps({
        "approach": "Approach 1",
        "error_type": "test_failure",
        "error_summary": "Error 1",
        "files_touched": ["File1.java"],
        "hypothesis": "Hypothesis 1"
    })
    record2 = json.dumps({
        "approach": "Approach 2",
        "error_type": "build_failure",
        "error_summary": "Error 2",
        "files_touched": ["File2.java"],
        "hypothesis": "Hypothesis 2"
    })

    cmd_append("acme", "test-feature", "ACME-123", record1)
    cmd_append("acme", "test-feature", "ACME-123", record2)

    # Read back
    cmd_load("acme", "test-feature", "ACME-123")

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["attempts"] == 2
    assert len(output["records"]) == 2
    assert output["records"][0]["approach"] == "Approach 1"
    assert output["records"][1]["approach"] == "Approach 2"
    assert output["excluded_approaches"] == ["Approach 1", "Approach 2"]


def test_read_returns_empty_list_for_missing_ledger(tmp_path, monkeypatch, capsys):
    """Read returns empty list for missing ledger, not crash."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    cmd_load("acme", "nonexistent-feature", "ACME-999")

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["attempts"] == 0
    assert output["records"] == []
    assert output["excluded_approaches"] == []


def test_path_uses_project_scoped_structure(tmp_path, monkeypatch):
    """Path uses memory/features/{project}/{slug}/ structure."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    record_json = json.dumps({
        "approach": "Test approach",
        "error_type": "test_failure",
        "error_summary": "Test error",
        "files_touched": ["Test.java"],
        "hypothesis": "Test hypothesis"
    })

    cmd_append("acme", "test-feature", "ACME-123", record_json)

    # Verify correct path
    correct_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "failure-ledger-ACME-123.json"
    assert correct_path.exists()

    # Verify wrong path does NOT exist
    wrong_path = tmp_path / "memory" / "features" / "test-feature" / "failure-ledger-ACME-123.json"
    assert not wrong_path.exists()


def test_check_detects_similar_approach(tmp_path, monkeypatch, capsys):
    """Check detects when new approach overlaps >70% with prior failure."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    # Add a failed approach
    record_json = json.dumps({
        "approach": "Added null check in validate method",
        "error_type": "test_failure",
        "error_summary": "NPE at line 42",
        "files_touched": ["UserService.java"],
        "hypothesis": "Mock not configured"
    })
    cmd_append("acme", "test-feature", "ACME-123", record_json)

    # Check similar approach
    with pytest.raises(SystemExit) as exc_info:
        cmd_check("acme", "test-feature", "ACME-123", "Added null check in validate")

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["similar"] is True
    assert output["overlap"] > 0.7
    assert "70%+ word overlap" in output["reason"]


def test_check_allows_different_approach(tmp_path, monkeypatch, capsys):
    """Check allows when new approach has <70% overlap with prior failures."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    # Add a failed approach
    record_json = json.dumps({
        "approach": "Added null check in validate method",
        "error_type": "test_failure",
        "error_summary": "NPE at line 42",
        "files_touched": ["UserService.java"],
        "hypothesis": "Mock not configured"
    })
    cmd_append("acme", "test-feature", "ACME-123", record_json)

    # Check completely different approach
    cmd_check("acme", "test-feature", "ACME-123", "Refactored database connection pooling")

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["similar"] is False
    assert "no significant overlap" in output["reason"].lower()


def test_excluded_approaches_cumulative(tmp_path, monkeypatch):
    """Excluded approaches list grows cumulatively with each failure."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    record1 = json.dumps({
        "approach": "Approach 1",
        "error_type": "test_failure",
        "error_summary": "Error 1",
        "files_touched": ["File1.java"],
        "hypothesis": "Hypothesis 1"
    })
    record2 = json.dumps({
        "approach": "Approach 2",
        "error_type": "test_failure",
        "error_summary": "Error 2",
        "files_touched": ["File2.java"],
        "hypothesis": "Hypothesis 2"
    })

    cmd_append("acme", "test-feature", "ACME-123", record1)
    cmd_append("acme", "test-feature", "ACME-123", record2)

    ledger_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "failure-ledger-ACME-123.json"
    records = json.loads(ledger_path.read_text())

    # First record excludes only itself
    assert records[0]["excluded_approaches"] == ["Approach 1"]

    # Second record excludes both prior and itself
    assert records[1]["excluded_approaches"] == ["Approach 1", "Approach 2"]


def test_atomic_write_with_tmp_file(tmp_path, monkeypatch):
    """Save uses .tmp file for atomic write."""
    monkeypatch.setattr("failure_ledger.REPO_ROOT", tmp_path)

    record_json = json.dumps({
        "approach": "Test approach",
        "error_type": "test_failure",
        "error_summary": "Test error",
        "files_touched": ["Test.java"],
        "hypothesis": "Test hypothesis"
    })

    cmd_append("acme", "test-feature", "ACME-123", record_json)

    # Verify final file exists
    ledger_path = tmp_path / "memory" / "features" / "acme" / "test-feature" / "failure-ledger-ACME-123.json"
    assert ledger_path.exists()

    # Verify tmp file was cleaned up
    tmp_path_file = ledger_path.with_suffix(".tmp")
    assert not tmp_path_file.exists()
