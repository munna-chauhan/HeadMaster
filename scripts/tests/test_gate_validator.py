#!/usr/bin/env python
"""Tests for gate_validator.py — gate string detection and error messaging."""
import json
import tempfile
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from gate_validator import validate_gate
from gate_constants import GATE_PRD_APPROVED, GATE_TDD_APPROVED, GATE_ARCH_LOCKED


def _tmp(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


def test_prd_approved_present():
    path = _tmp(f"| PRD Status | {GATE_PRD_APPROVED.split(': ')[1]} |\n")
    try:
        # Write full gate string
        path2 = _tmp(f"Table\n{GATE_PRD_APPROVED}\nEnd")
        ok, msg = validate_gate(path2, "PRD_APPROVED")
        assert ok, f"Should pass: {msg}"
        print("[PASS] PRD_APPROVED detected")
    finally:
        os.unlink(path)
        os.unlink(path2)


def test_prd_approved_missing():
    path = _tmp("| PRD Status | DRAFT |\n")
    try:
        ok, msg = validate_gate(path, "PRD_APPROVED")
        assert not ok
        print(f"[PASS] PRD_APPROVED missing detected: {msg}")
    finally:
        os.unlink(path)


def test_case_sensitivity_error():
    """Wrong case should produce a helpful error message."""
    path = _tmp("PRD Status: Approved\n")
    try:
        ok, msg = validate_gate(path, "PRD_APPROVED")
        assert not ok
        assert "case-sensitive" in msg.lower() or "found" in msg.lower(), f"Expected case hint in: {msg}"
        print(f"[PASS] Case error message: {msg}")
    finally:
        os.unlink(path)


def test_tdd_approved():
    path = _tmp(f"{GATE_TDD_APPROVED}\n")
    try:
        ok, msg = validate_gate(path, "TDD_APPROVED")
        assert ok
        print("[PASS] TDD_APPROVED detected")
    finally:
        os.unlink(path)


def test_arch_locked():
    path = _tmp(f"Section 1\n{GATE_ARCH_LOCKED}\nSection 2\n")
    try:
        ok, msg = validate_gate(path, "ARCH_LOCKED")
        assert ok
        print("[PASS] ARCH_LOCKED detected")
    finally:
        os.unlink(path)


def test_missing_artifact():
    ok, msg = validate_gate("/nonexistent/file.md", "PRD_APPROVED")
    assert not ok
    assert "not found" in msg.lower()
    print(f"[PASS] Missing artifact: {msg}")


def test_unknown_gate_key():
    path = _tmp("anything")
    try:
        ok, msg = validate_gate(path, "INVALID_KEY")
        assert not ok
        assert "unknown gate key" in msg.lower()
        print(f"[PASS] Unknown key: {msg}")
    finally:
        os.unlink(path)


if __name__ == "__main__":
    print("Running gate_validator tests...\n")
    test_prd_approved_present()
    test_prd_approved_missing()
    test_case_sensitivity_error()
    test_tdd_approved()
    test_arch_locked()
    test_missing_artifact()
    test_unknown_gate_key()
    print("\n[PASS] All gate_validator tests passed")
