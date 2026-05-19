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
"""Unit tests for story_phase_complete.py"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from story_phase_complete import _update_loop_state, _checkpoint_loop_state


def _state_file(tmp_path: Path) -> Path:
    p = tmp_path / "memory" / "features" / "proj" / "slug" / "loop_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# _update_loop_state
# ---------------------------------------------------------------------------

def test_start_writes_in_progress(tmp_path):
    sf = _state_file(tmp_path)
    _update_loop_state(sf, "PROJ-1", [], "IN_PROGRESS")
    state = json.loads(sf.read_text())
    story = state["stories"]["PROJ-1"]
    assert story["status"] == "IN_PROGRESS"
    assert story["phases_completed"] == []


def test_complete_writes_status_and_phases(tmp_path):
    sf = _state_file(tmp_path)
    _update_loop_state(sf, "PROJ-1", [], "IN_PROGRESS")
    _update_loop_state(sf, "PROJ-1", ["A", "B"], "COMPLETE")
    story = json.loads(sf.read_text())["stories"]["PROJ-1"]
    assert story["status"] == "COMPLETE"
    assert story["phases_completed"] == ["A", "B"]


def test_phases_are_deduped_and_sorted(tmp_path):
    sf = _state_file(tmp_path)
    _update_loop_state(sf, "PROJ-1", ["B", "A", "A"], "COMPLETE")
    story = json.loads(sf.read_text())["stories"]["PROJ-1"]
    assert story["phases_completed"] == ["A", "B"]


# ---------------------------------------------------------------------------
# _checkpoint_loop_state
# ---------------------------------------------------------------------------

def test_checkpoint_adds_phase_without_changing_status(tmp_path):
    sf = _state_file(tmp_path)
    _update_loop_state(sf, "PROJ-2", [], "IN_PROGRESS")
    _checkpoint_loop_state(sf, "PROJ-2", "A")
    story = json.loads(sf.read_text())["stories"]["PROJ-2"]
    assert story["phases_completed"] == ["A"]
    assert story["status"] == "IN_PROGRESS"


def test_checkpoint_is_idempotent(tmp_path):
    sf = _state_file(tmp_path)
    _update_loop_state(sf, "PROJ-2", [], "IN_PROGRESS")
    _checkpoint_loop_state(sf, "PROJ-2", "A")
    _checkpoint_loop_state(sf, "PROJ-2", "A")
    story = json.loads(sf.read_text())["stories"]["PROJ-2"]
    assert story["phases_completed"] == ["A"]


def test_checkpoint_creates_story_entry_if_absent(tmp_path):
    sf = _state_file(tmp_path)
    _checkpoint_loop_state(sf, "PROJ-3", "A")
    story = json.loads(sf.read_text())["stories"]["PROJ-3"]
    assert story["phases_completed"] == ["A"]
    assert story["status"] == "IN_PROGRESS"


def test_checkpoint_does_not_overwrite_complete_status(tmp_path):
    """A checkpoint call after complete must not revert status to IN_PROGRESS."""
    sf = _state_file(tmp_path)
    _update_loop_state(sf, "PROJ-4", ["A", "B"], "COMPLETE")
    _checkpoint_loop_state(sf, "PROJ-4", "A")
    story = json.loads(sf.read_text())["stories"]["PROJ-4"]
    # status stays COMPLETE — checkpoint only touches phases_completed
    assert story["status"] == "COMPLETE"
    assert "A" in story["phases_completed"]


def test_checkpoint_accumulates_multiple_phases(tmp_path):
    sf = _state_file(tmp_path)
    _update_loop_state(sf, "PROJ-5", [], "IN_PROGRESS")
    _checkpoint_loop_state(sf, "PROJ-5", "A")
    _checkpoint_loop_state(sf, "PROJ-5", "B")
    story = json.loads(sf.read_text())["stories"]["PROJ-5"]
    assert story["phases_completed"] == ["A", "B"]
    assert story["status"] == "IN_PROGRESS"


def test_updated_timestamp_written_by_checkpoint(tmp_path):
    sf = _state_file(tmp_path)
    _checkpoint_loop_state(sf, "PROJ-6", "A")
    story = json.loads(sf.read_text())["stories"]["PROJ-6"]
    assert "updated" in story
