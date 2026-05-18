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
"""Tests for extract_phase_learnings.py and failure_ledger.py summarize subcommand."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_phase_learnings import _build_entries, _load_records
from failure_ledger import cmd_summarize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record(error_type: str, hypothesis: str = "", error_summary: str = "") -> dict:
    return {
        "approach": "some approach",
        "error_type": error_type,
        "error_summary": error_summary,
        "hypothesis": hypothesis,
        "files_touched": [],
        "story_key": "TEST-1",
        "attempt": 1,
    }


def _make_ledger(tmp_path: Path, project: str, slug: str, story_key: str, records: list) -> Path:
    p = tmp_path / "memory" / "features" / project / slug
    p.mkdir(parents=True)
    path = p / f"failure-ledger-{story_key}.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _load_records
# ---------------------------------------------------------------------------

def test_load_records_missing_file_returns_empty(tmp_path, monkeypatch):
    import extract_phase_learnings
    monkeypatch.setattr(extract_phase_learnings, "REPO_ROOT", tmp_path)
    assert _load_records("proj", "slug", "KEY-1") == []


def test_load_records_reads_ledger(tmp_path, monkeypatch):
    import extract_phase_learnings
    monkeypatch.setattr(extract_phase_learnings, "REPO_ROOT", tmp_path)
    _make_ledger(tmp_path, "proj", "slug", "KEY-1", [_record("test_failure")])
    records = _load_records("proj", "slug", "KEY-1")
    assert len(records) == 1
    assert records[0]["error_type"] == "test_failure"


def test_load_records_invalid_json_returns_empty(tmp_path, monkeypatch):
    import extract_phase_learnings
    monkeypatch.setattr(extract_phase_learnings, "REPO_ROOT", tmp_path)
    p = tmp_path / "memory" / "features" / "proj" / "slug"
    p.mkdir(parents=True)
    (p / "failure-ledger-KEY-1.json").write_text("not json", encoding="utf-8")
    assert _load_records("proj", "slug", "KEY-1") == []


# ---------------------------------------------------------------------------
# _build_entries
# ---------------------------------------------------------------------------

def test_build_entries_empty_records():
    assert _build_entries([]) == []


def test_build_entries_developer_for_build_failure():
    entries = _build_entries([_record("build_failure", hypothesis="circular import in module")])
    assert len(entries) == 1
    agent, entry = entries[0]
    assert agent == "developer"
    assert "build_failure" in entry
    assert "circular import" in entry


def test_build_entries_qa_engineer_for_ac_coverage_gap():
    entries = _build_entries([_record("ac_coverage_gap", hypothesis="no file change for AC domain")])
    assert len(entries) == 1
    agent, entry = entries[0]
    assert agent == "qa-engineer"
    assert "ac_coverage_gap" in entry


def test_build_entries_deduplicates_same_error_type():
    records = [
        _record("test_failure", hypothesis="mock not configured"),
        _record("test_failure", hypothesis="different test setup"),
    ]
    entries = _build_entries(records)
    assert len(entries) == 1


def test_build_entries_multiple_error_types():
    records = [
        _record("build_failure", hypothesis="bad import"),
        _record("test_failure", hypothesis="wrong mock"),
        _record("ac_coverage_gap", hypothesis="missing file change"),
    ]
    entries = _build_entries(records)
    assert len(entries) == 3
    agents = [a for a, _ in entries]
    assert agents.count("developer") == 2
    assert agents.count("qa-engineer") == 1


def test_build_entries_prefers_hypothesis_over_summary():
    entries = _build_entries([_record("runtime_error", hypothesis="null guard missing", error_summary="NPE at line 42")])
    _, entry = entries[0]
    assert "null guard" in entry
    assert "NPE" not in entry


def test_build_entries_falls_back_to_error_summary():
    entries = _build_entries([_record("runtime_error", hypothesis="", error_summary="NPE at line 42")])
    _, entry = entries[0]
    assert "NPE" in entry


def test_build_entries_entry_truncated_at_80_chars():
    long_hypothesis = "a" * 200
    entries = _build_entries([_record("test_failure", hypothesis=long_hypothesis)])
    _, entry = entries[0]
    # The detail portion is capped at 80 chars
    assert len(entry) < 120  # "Phase A test_failure retry: " + 80 chars


# ---------------------------------------------------------------------------
# failure_ledger cmd_summarize
# ---------------------------------------------------------------------------

def test_summarize_no_records(tmp_path, monkeypatch, capsys):
    import failure_ledger
    monkeypatch.setattr(failure_ledger, "REPO_ROOT", tmp_path)
    cmd_summarize("proj", "slug", "KEY-1")
    out = json.loads(capsys.readouterr().out)
    assert out["attempts"] == 0
    assert out["error_types"] == {}
    assert out["hypotheses"] == []


def test_summarize_counts_error_types(tmp_path, monkeypatch, capsys):
    import failure_ledger
    monkeypatch.setattr(failure_ledger, "REPO_ROOT", tmp_path)
    records = [
        {**_record("build_failure", hypothesis="bad import"), "timestamp": "t", "excluded_approaches": [], "suggested_alternatives": []},
        {**_record("build_failure", hypothesis="other issue"), "timestamp": "t", "excluded_approaches": [], "suggested_alternatives": []},
        {**_record("test_failure", hypothesis="mock wrong"), "timestamp": "t", "excluded_approaches": [], "suggested_alternatives": []},
    ]
    _make_ledger(tmp_path, "proj", "slug", "KEY-1", records)
    cmd_summarize("proj", "slug", "KEY-1")
    out = json.loads(capsys.readouterr().out)
    assert out["attempts"] == 3
    assert out["error_types"]["build_failure"] == 2
    assert out["error_types"]["test_failure"] == 1
    assert "bad import" in out["hypotheses"]


def test_summarize_skips_empty_hypotheses(tmp_path, monkeypatch, capsys):
    import failure_ledger
    monkeypatch.setattr(failure_ledger, "REPO_ROOT", tmp_path)
    records = [
        {**_record("build_failure", hypothesis=""), "timestamp": "t", "excluded_approaches": [], "suggested_alternatives": []},
    ]
    _make_ledger(tmp_path, "proj", "slug", "KEY-1", records)
    cmd_summarize("proj", "slug", "KEY-1")
    out = json.loads(capsys.readouterr().out)
    assert out["hypotheses"] == []
