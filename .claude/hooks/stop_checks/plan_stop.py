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
"""Stop hook for plan phase — verifies PRD is approved before allowing stop.

Usage:
    sh .claude/hooks/stop_checks/plan_stop.py <slug>

Returns JSON: {"ok": true} or {"ok": false, "reason": "..."}
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    try:
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        payload = {}

    # Loop prevention: if stop_hook_active, pass immediately
    if payload.get("stop_hook_active"):
        print(json.dumps({"ok": True}))
        sys.exit(0)

    # Escape hatch: agent is asking a question
    last_msg = payload.get("last_assistant_message", "")
    if "AskUserQuestion" in last_msg:
        print(json.dumps({"ok": True}))
        sys.exit(0)

    # Load active project from config
    try:
        import yaml
        config_path = ROOT / "config.yml"
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        project = config["projects"]["active"]
    except Exception as e:
        print(json.dumps({"ok": False, "reason": f"Config load failed: {e}"}))
        sys.exit(0)

    # Check PRD status in last 200 bytes
    prd_path = ROOT / "docs" / "features" / project / slug / "planning" / "PRD.md"
    if not prd_path.exists():
        print(json.dumps({"ok": False, "reason": "PRD not finalized: file missing"}))
        sys.exit(0)

    tail = prd_path.read_bytes()[-200:].decode("utf-8", errors="ignore")
    if "PRD Status: APPROVED" in tail:
        print(json.dumps({"ok": True}))
    else:
        print(json.dumps({"ok": False, "reason": "PRD not finalized: status not APPROVED"}))

    sys.exit(0)


if __name__ == "__main__":
    main()