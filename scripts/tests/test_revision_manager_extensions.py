#!/bin/sh
""":"
for c in python3 py3 python py; do command -v "$c" >/dev/null 2>&1 && exec "$c" "$0" "$@"; done
for d in /c/Python* /c/Python*/Python* "/c/Program Files/Python"* "/c/Program Files/Python"*/Python* "/c/Program Files (x86)/Python"* "/c/Program Files (x86)/Python"*/Python* "$HOME/AppData/Local/Programs/Python/Python"* "$LOCALAPPDATA/Programs/Python/Python"*; do
  for n in python.exe python3.exe; do
    [ -x "$d/$n" ] && exec "$d/$n" "$0" "$@"
  done
done
echo "[HeadMaster] No python interpreter found" >&2
exit 127
":"""
"""Tests for revision_manager.py extensions: current_revision block, revisions[] history."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import revision_manager


def _make_state(tmp: Path, project: str, slug: str, state: dict) -> Path:
    d = tmp / "memory" / "features" / project / slug
    d.mkdir(parents=True)
    sf = d / "loop_state.json"
    sf.write_text(json.dumps(state), encoding="utf-8")
    return sf


def _make_docs(tmp: Path, project: str, slug: str) -> Path:
    d = tmp / "docs" / "features" / project / slug
    d.mkdir(parents=True)
    return d


def test_reopen_populates_current_revision(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(revision_manager, "REPO_ROOT", tmp_path)
    project, slug = "p", "s"
    sf = _make_state(tmp_path, project, slug, {
        "artifacts": {"planning/PRD.md": {"status": "approved"}},
        "pipeline": {"phase": "planning", "stage": "complete"},
    })
    _make_docs(tmp_path, project, slug)

    revision_manager.cmd_reopen(project, slug, "planning", "minor", "test reopen")

    state = json.loads(sf.read_text())
    cr = state["pipeline"].get("current_revision")
    assert cr is not None, "current_revision should be set"
    assert cr["stage"] == "planning"
    assert "planning/PRD.md" in cr["artifacts_in_scope"]
    assert "rev_id" in cr
    assert "opened" in cr
    print("[PASS] cmd_reopen sets current_revision")


def test_reopen_appends_revisions_history(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(revision_manager, "REPO_ROOT", tmp_path)
    project, slug = "p", "s"
    sf = _make_state(tmp_path, project, slug, {
        "artifacts": {"planning/PRD.md": {"status": "approved"}},
        "pipeline": {},
    })
    _make_docs(tmp_path, project, slug)

    revision_manager.cmd_reopen(project, slug, "planning", "standard", "first revision")

    state = json.loads(sf.read_text())
    revisions = state.get("revisions", [])
    assert len(revisions) == 1
    assert revisions[0]["stage"] == "planning"
    assert revisions[0]["scope"] == "standard"
    assert revisions[0]["closed"] is None
    print("[PASS] cmd_reopen appends to revisions[]")


def test_close_clears_current_revision(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(revision_manager, "REPO_ROOT", tmp_path)
    project, slug = "p", "s"
    sf = _make_state(tmp_path, project, slug, {
        "artifacts": {"planning/PRD.md": {"status": "revision"}},
        "pipeline": {
            "revision_open": True,
            "revision_id": "REV-001",
            "revision_stage": "planning",
            "revision_cascade": [],
            "revision_opened": "2026-01-01T00:00:00+00:00",
            "current_revision": {"rev_id": "REV-001", "stage": "planning"},
        },
        "revisions": [{"rev_id": "REV-001", "stage": "planning", "closed": None}],
    })
    log = tmp_path / "docs" / "features" / project / slug / "REVISION_NOTES.md"
    log.parent.mkdir(parents=True)
    log.write_text("## REV-001 [2026-01-01] planning OPEN\n", encoding="utf-8")

    revision_manager.cmd_close(project, slug, "REV-001")

    state = json.loads(sf.read_text())
    assert state["pipeline"].get("current_revision") is None
    assert state["pipeline"].get("revision_open") is None
    assert state["revisions"][0]["closed"] is not None
    print("[PASS] cmd_close clears current_revision and sets closed date")


def test_current_revision_command_no_revision(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(revision_manager, "REPO_ROOT", tmp_path)
    project, slug = "p", "s"
    _make_state(tmp_path, project, slug, {"pipeline": {}})

    with patch("sys.argv", ["revision_manager.py", "current-revision", project, slug]):
        revision_manager.main()

    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["current_revision"] is None
    print("[PASS] current-revision command returns null when no revision open")


def test_current_revision_command_with_revision(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(revision_manager, "REPO_ROOT", tmp_path)
    project, slug = "p", "s"
    _make_state(tmp_path, project, slug, {
        "pipeline": {
            "current_revision": {
                "rev_id": "REV-002",
                "stage": "design",
                "artifacts_in_scope": ["design/TDD_foo.md"],
                "artifacts_out_of_scope": [],
                "opened": "2026-05-01T00:00:00+00:00",
            }
        }
    })

    with patch("sys.argv", ["revision_manager.py", "current-revision", project, slug]):
        revision_manager.main()

    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["current_revision"]["rev_id"] == "REV-002"
    assert data["current_revision"]["stage"] == "design"
    print("[PASS] current-revision command returns current_revision when open")


if __name__ == "__main__":
    import tempfile, types
    # Can't easily run without pytest fixtures; use pytest instead
    print("Run with: pytest scripts/tests/test_revision_manager_extensions.py -v")
