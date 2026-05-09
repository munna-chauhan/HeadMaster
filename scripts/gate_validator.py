#!/usr/bin/env python
"""Validate gate strings in pipeline artifacts.

Usage:
    python scripts/gate_validator.py <artifact_path> <gate_key>

Gate keys: PRD_APPROVED | ARCH_LOCKED | TDD_APPROVED | SYSTEM_REVIEW_PASS

Returns: 0 if gate string found, 1 if not (with diagnostic to stderr), 2 on usage error.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gate_constants import (
    GATE_PRD_APPROVED, GATE_ARCH_LOCKED, GATE_TDD_APPROVED, GATE_SYSTEM_REVIEW_PASS,
)

GATE_MAP = {
    "PRD_APPROVED":       GATE_PRD_APPROVED,
    "ARCH_LOCKED":        GATE_ARCH_LOCKED,
    "TDD_APPROVED":       GATE_TDD_APPROVED,
    "SYSTEM_REVIEW_PASS": GATE_SYSTEM_REVIEW_PASS,
}


def validate_gate(artifact_path: str, gate_key: str) -> tuple[bool, str]:
    expected = GATE_MAP.get(gate_key.upper())
    if expected is None:
        return False, f"Unknown gate key '{gate_key}'. Valid: {list(GATE_MAP)}"

    path = Path(artifact_path)
    if not path.exists():
        return False, f"Artifact not found: {artifact_path}"

    content = path.read_text(encoding="utf-8")
    if expected in content:
        return True, ""

    lower_expected = expected.lower()
    for line in content.splitlines():
        if lower_expected in line.lower():
            return False, f"Expected '{expected}' — found '{line.strip()}'. Gate strings are case-sensitive."

    return False, f"Gate string '{expected}' not found in {artifact_path}"


def main():
    if len(sys.argv) != 3:
        print("Usage: gate_validator.py <artifact_path> <gate_key>", file=sys.stderr)
        sys.exit(2)

    found, msg = validate_gate(sys.argv[1], sys.argv[2])
    if found:
        sys.exit(0)
    print(f"[gate-validator] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
