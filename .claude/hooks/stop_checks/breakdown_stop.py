#!/usr/bin/env python3
"""Deterministic stop check for /breakdown skill. Replaces haiku agent."""
import json
import sys
from pathlib import Path

def main():
    # Check if stop hook is already active (prevent infinite loops)
    try:
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        if payload.get("stop_hook_active"):
            print(json.dumps({"ok": True}))
            sys.exit(0)
    except Exception:
        payload = {}

    args = sys.argv[1] if len(sys.argv) > 1 else ""
    slug = args.strip()
    if not slug:
        features = Path("docs/features")
        if features.exists():
            dirs = [d.name for d in features.iterdir() if d.is_dir()]
            slug = dirs[0] if len(dirs) == 1 else ""

    if not slug:
        print(json.dumps({"ok": False, "reason": "Cannot determine feature slug"}))
        sys.exit(0)

    breakdown = Path(f"docs/features/{slug}/breakdown/JIRA_BREAKDOWN.md")
    if breakdown.exists():
        content = breakdown.read_text(encoding="utf-8", errors="ignore")
        if "Push Status:" in content:
            print(json.dumps({"ok": True}))
            sys.exit(0)

    # Check if waiting for user input (payload already loaded above)
    last_msg = payload.get("last_assistant_message", "")
    if ("AskUserQuestion" in last_msg or
        "ToolSearch" in last_msg and "AskUserQuestion" in last_msg or
        '"questions":' in last_msg or
        "HALT" in last_msg):
        print(json.dumps({"ok": True}))
        sys.exit(0)

    print(json.dumps({"ok": False, "reason": "JIRA_BREAKDOWN.md missing or incomplete"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
