#!/usr/bin/env python3
"""Deterministic stop check for /execute skill. Replaces haiku agent."""
import json
import sys
from pathlib import Path

def main():
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
    if not breakdown.exists():
        print(json.dumps({"ok": False, "reason": "JIRA_BREAKDOWN.md missing"}))
        sys.exit(0)

    content = breakdown.read_text(encoding="utf-8", errors="ignore")

    # Check if all stories are COMPLETE or DEFERRED
    has_incomplete = False
    for line in content.split("\n"):
        if "IN PROGRESS" in line or "SCANNING" in line or "IN REVIEW" in line or "IN QA" in line:
            # Active work — ok to pause
            print(json.dumps({"ok": True}))
            sys.exit(0)
        if "NEW" in line and "|" in line:
            has_incomplete = True

    # Check system review exists (all stories done)
    sys_review = Path(f"docs/features/{slug}/retrospective/system-review.md")
    if sys_review.exists() and not has_incomplete:
        print(json.dumps({"ok": True}))
        sys.exit(0)

    # Check if waiting for user input
    try:
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        last_msg = payload.get("last_assistant_message", "")
        if "AskUserQuestion" in last_msg or "ESCALATED" in last_msg or "PR created" in last_msg:
            print(json.dumps({"ok": True}))
            sys.exit(0)
    except Exception:
        pass

    if has_incomplete:
        print(json.dumps({"ok": False, "reason": "Stories remain NEW with unblocked dependencies"}))
    else:
        print(json.dumps({"ok": True}))
    sys.exit(0)

if __name__ == "__main__":
    main()
