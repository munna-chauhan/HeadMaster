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
# Gate string constants — kept for reference only.
# Gate validation now reads loop_state.json via gate_validator.py, not artifact content.

GATE_PRD_APPROVED       = "PRD Status: APPROVED"
GATE_ARCH_LOCKED        = "Architecture Locked: YES"
GATE_TDD_APPROVED       = "TDD Status: APPROVED"
GATE_SYSTEM_REVIEW_PASS = "System Review: PASS"
