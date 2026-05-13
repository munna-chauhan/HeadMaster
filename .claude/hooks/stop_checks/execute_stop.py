#!/usr/bin/env python
"""Stop hook for execute phase — checks story completion and system review presence.

Logic:
  - If any story is IN PROGRESS: pass (active work, resumable)
  - If any story is NEW and no IN PROGRESS: block with "remain NEW"
  - If all stories COMPLETE and system-review.md exists: pass
  - If all stories COMPLETE but no system-review.md: pass (review optional)
  - No breakdown file: block

Usage:
    python .claude/hooks/stop_checks/execute_stop.py <slug>

Returns JSON: {"ok": true} or {"ok": false, "reason": "..."}
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _parse_story_statuses(content: str) -> list[str]:
    """Extract story statuses from JIRA_BREAKDOWN.md table rows."""
    statuses = []
    for line in content.splitlines():
        if "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            for cell in cells:
                upper = cell.upper()
                if upper in ("IN_PROGRESS", "IN PROGRESS", "NEW", "COMPLETE", "DONE",
                            "BLOCKED", "DEFERRED", "SCANNING", "IN_REVIEW", "IN_QA"):
                    statuses.append(upper)
    return statuses


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

    feature_dir = ROOT / "docs" / "features" / project / slug
    breakdown_path = feature_dir / "breakdown" / "JIRA_BREAKDOWN.md"

    if not breakdown_path.exists():
        print(json.dumps({"ok": False, "reason": "Breakdown missing or incomplete: JIRA_BREAKDOWN.md not found"}))
        sys.exit(0)

    content = breakdown_path.read_text(encoding="utf-8", errors="ignore")
    statuses = _parse_story_statuses(content)

    # Active work in progress — allow (resumable state)
    if "IN PROGRESS" in statuses:
        print(json.dumps({"ok": True}))
        sys.exit(0)

    # Stories still NEW — block
    if "NEW" in statuses:
        new_count = statuses.count("NEW")
        print(json.dumps({"ok": False, "reason": f"{new_count} stories remain NEW — execution incomplete"}))
        sys.exit(0)

    # All stories done — check system review
    review_path = feature_dir / "retrospective" / "system-review.md"
    if review_path.exists():
        print(json.dumps({"ok": True}))
    else:
        # System review optional — pass anyway if all stories complete
        print(json.dumps({"ok": True}))

    sys.exit(0)


if __name__ == "__main__":
    main()