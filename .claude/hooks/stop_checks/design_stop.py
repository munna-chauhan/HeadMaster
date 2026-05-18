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
"""Stop hook for design phase — verifies design artifact is complete before allowing stop.

Passes if:
  - IMPLEMENTATION_BRIEF.md exists with >= 5 sections (lite/xs tier), OR
  - TDD_REVIEW.md exists with APPROVED verdict (full tier)

Usage:
    sh .claude/hooks/stop_checks/design_stop.py <slug>

Returns JSON: {"ok": true} or {"ok": false, "reason": "..."}
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _count_sections(text: str) -> int:
    return len(re.findall(r'^##\s+', text, re.MULTILINE))


def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    try:
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        payload = {}

    # Loop prevention
    if payload.get("stop_hook_active"):
        print(json.dumps({"ok": True}))
        sys.exit(0)

    # Escape hatch
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

    design_dir = ROOT / "docs" / "features" / project / slug / "design"

    # Check TDD_REVIEW.md (full tier)
    review_path = design_dir / "TDD_REVIEW.md"
    if review_path.exists():
        content = review_path.read_text(encoding="utf-8", errors="ignore")
        # Check last 500 bytes for APPROVED verdict
        tail = review_path.read_bytes()[-500:].decode("utf-8", errors="ignore")
        if "APPROVED" in tail:
            print(json.dumps({"ok": True}))
            sys.exit(0)
        # Also check old-format inline verdict
        if re.search(r'Verdict:\s*APPROVED', content):
            print(json.dumps({"ok": True}))
            sys.exit(0)
        # Review exists but not approved — block
        print(json.dumps({"ok": False, "reason": "Design not finalized: TDD_REVIEW.md verdict not APPROVED"}))
        sys.exit(0)

    # Check IMPLEMENTATION_BRIEF.md (lite/xs tier)
    brief_path = design_dir / "IMPLEMENTATION_BRIEF.md"
    if brief_path.exists():
        content = brief_path.read_text(encoding="utf-8", errors="ignore")
        section_count = _count_sections(content)
        if section_count >= 5:
            print(json.dumps({"ok": True}))
        else:
            print(json.dumps({"ok": False, "reason": f"Design not finalized: IMPLEMENTATION_BRIEF.md has {section_count} sections (need ≥5)"}))
        sys.exit(0)

    print(json.dumps({"ok": False, "reason": "Design not finalized: no design artifact found"}))
    sys.exit(0)


if __name__ == "__main__":
    main()