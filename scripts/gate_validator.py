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
"""Validate pipeline gates via loop_state.json.

Usage:
    sh scripts/gate_validator.py --project <p> --slug <s> PRD_APPROVED
    sh scripts/gate_validator.py --project <p> --slug <s> TDD_APPROVED --name <tdd-name>
    sh scripts/gate_validator.py --project <p> --slug <s> ARCH_LOCKED
    sh scripts/gate_validator.py --project <p> --slug <s> SYSTEM_REVIEW_PASS

Returns: 0 if gate passes, 1 if not (diagnostic to stderr), 2 on usage error.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def validate_gate(project: str, slug: str, gate_key: str, name: str = None, repo_root: Path = None) -> tuple[bool, str]:
    root = Path(repo_root) if repo_root else REPO_ROOT
    state_file = root / "memory" / "features" / project / slug / "loop_state.json"
    if not state_file.exists():
        return False, f"loop_state.json not found for {project}/{slug}"

    state = json.loads(state_file.read_text(encoding="utf-8"))
    key = gate_key.upper()

    if key == "PRD_APPROVED":
        status = state.get("artifacts", {}).get("planning/PRD.md", {}).get("status")
        if status == "approved":
            return True, ""
        return False, f"planning/PRD.md status is '{status or 'not set'}' — run /plan {slug} to get PRD approved"

    if key == "TDD_APPROVED":
        if not name:
            return False, "TDD_APPROVED requires --name <tdd-name>"
        artifact_key = f"design/TDD_{name}.md"
        status = state.get("artifacts", {}).get(artifact_key, {}).get("status")
        if status == "approved":
            return True, ""
        return False, f"{artifact_key} status is '{status or 'not set'}' — run /design {slug} to get TDD approved"

    if key == "ARCH_LOCKED":
        arch_status = state.get("design_stages", {}).get("architect")
        if arch_status == "complete":
            return True, ""
        return False, f"design_stages.architect is '{arch_status or 'not set'}' — architect stage not complete"

    if key == "SYSTEM_REVIEW_PASS":
        review_status = state.get("review", {}).get("status")
        if review_status == "PASS":
            return True, ""
        return False, f"review.status is '{review_status or 'not set'}' — system review has not passed"

    return False, f"Unknown gate key '{gate_key}'. Valid: PRD_APPROVED, TDD_APPROVED, ARCH_LOCKED, SYSTEM_REVIEW_PASS"


def main():
    parser = argparse.ArgumentParser(description="Validate pipeline gates via loop_state.json")
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument("--slug",    required=True, help="Feature slug")
    parser.add_argument("--name",    help="TDD name (required for TDD_APPROVED)")
    parser.add_argument("gate_key",  help="PRD_APPROVED | TDD_APPROVED | ARCH_LOCKED | SYSTEM_REVIEW_PASS")
    args = parser.parse_args()

    found, msg = validate_gate(args.project, args.slug, args.gate_key, args.name)
    if found:
        sys.exit(0)
    print(f"[gate-validator] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
