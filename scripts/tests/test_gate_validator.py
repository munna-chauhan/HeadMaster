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
"""Tests for gate_validator.py — loop_state.json gate checks."""
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from gate_validator import validate_gate

PROJECT = "test-proj"
SLUG    = "test-slug"


def _write_state(state: dict) -> Path:
    tmpdir = Path(tempfile.mkdtemp())
    state_dir = tmpdir / "memory" / "features" / PROJECT / SLUG
    state_dir.mkdir(parents=True)
    (state_dir / "loop_state.json").write_text(json.dumps(state), encoding="utf-8")
    return tmpdir


def _v(state, gate_key, **kw):
    return validate_gate(PROJECT, SLUG, gate_key, repo_root=_write_state(state), **kw)


def test_prd_approved_present():
    ok, _ = _v({"artifacts": {"planning/PRD.md": {"status": "approved"}}}, "PRD_APPROVED")
    assert ok
    print("[PASS] PRD_APPROVED — approved")


def test_prd_approved_missing():
    ok, msg = _v({"artifacts": {"planning/PRD.md": {"status": "draft"}}}, "PRD_APPROVED")
    assert not ok and "draft" in msg
    print(f"[PASS] PRD_APPROVED — not approved: {msg}")


def test_prd_no_artifact():
    ok, msg = _v({}, "PRD_APPROVED")
    assert not ok and "not set" in msg
    print(f"[PASS] PRD_APPROVED — artifact absent: {msg}")


def test_tdd_approved_present():
    ok, _ = _v({"artifacts": {"design/TDD_search.md": {"status": "approved"}}}, "TDD_APPROVED", name="search")
    assert ok
    print("[PASS] TDD_APPROVED — approved")


def test_tdd_approved_requires_name():
    ok, msg = _v({}, "TDD_APPROVED")
    assert not ok and "--name" in msg
    print(f"[PASS] TDD_APPROVED — name required: {msg}")


def test_arch_locked_present():
    ok, _ = _v({"design_stages": {"architect": "complete"}}, "ARCH_LOCKED")
    assert ok
    print("[PASS] ARCH_LOCKED — complete")


def test_arch_locked_missing():
    ok, msg = _v({"design_stages": {"architect": "in_progress"}}, "ARCH_LOCKED")
    assert not ok and "in_progress" in msg
    print(f"[PASS] ARCH_LOCKED — not complete: {msg}")


def test_system_review_pass():
    ok, _ = _v({"review": {"status": "PASS"}}, "SYSTEM_REVIEW_PASS")
    assert ok
    print("[PASS] SYSTEM_REVIEW_PASS — passed")


def test_system_review_pending():
    ok, msg = _v({"review": {"status": "PENDING"}}, "SYSTEM_REVIEW_PASS")
    assert not ok and "PENDING" in msg
    print(f"[PASS] SYSTEM_REVIEW_PASS — pending: {msg}")


def test_missing_state_file():
    root = Path(tempfile.mkdtemp())  # empty — no loop_state.json
    ok, msg = validate_gate(PROJECT, SLUG, "PRD_APPROVED", repo_root=root)
    assert not ok and "not found" in msg
    print(f"[PASS] Missing state file: {msg}")


def test_unknown_gate_key():
    ok, msg = _v({}, "INVALID_KEY")
    assert not ok and "unknown gate key" in msg.lower()
    print(f"[PASS] Unknown key: {msg}")


if __name__ == "__main__":
    print("Running gate_validator tests...\n")
    test_prd_approved_present()
    test_prd_approved_missing()
    test_prd_no_artifact()
    test_tdd_approved_present()
    test_tdd_approved_requires_name()
    test_arch_locked_present()
    test_arch_locked_missing()
    test_system_review_pass()
    test_system_review_pending()
    test_missing_state_file()
    test_unknown_gate_key()
    print("\n[PASS] All gate_validator tests passed")
