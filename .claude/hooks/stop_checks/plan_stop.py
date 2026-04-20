#!/usr/bin/env python3
"""Deterministic stop check for /plan skill. Replaces haiku agent."""
import json
import sys
from pathlib import Path

def main():
    args = sys.argv[1] if len(sys.argv) > 1 else ""
    # Find slug from args or scan docs/features/
    slug = args.strip()
    if not slug:
        features = Path("docs/features")
        if features.exists():
            dirs = [d.name for d in features.iterdir() if d.is_dir()]
            slug = dirs[0] if len(dirs) == 1 else ""

    if not slug:
        print(json.dumps({"ok": False, "reason": "Cannot determine feature slug"}))
        sys.exit(0)

    prd = Path(f"docs/features/{slug}/planning/PRD.md")
    if prd.exists():
        tail = prd.read_bytes()[-200:].decode("utf-8", errors="ignore")
        if "PRD Status: APPROVED" in tail:
            print(json.dumps({"ok": True}))
            sys.exit(0)

    # Check if waiting for user input (read last context from stdin if available)
    try:
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        last_msg = payload.get("last_assistant_message", "")
        if "AskUserQuestion" in last_msg or "max_loops exceeded" in last_msg or "escalating to human" in last_msg:
            print(json.dumps({"ok": True}))
            sys.exit(0)
    except Exception:
        pass

    print(json.dumps({"ok": False, "reason": "PRD not finalized"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
