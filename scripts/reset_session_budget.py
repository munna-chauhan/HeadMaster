#!/usr/bin/env python3
"""
Manually reset session budget counter.

Usage:
    python scripts/reset_session_budget.py

Use this when:
- Starting a new feature (fresh turn count)
- After /handoff (clean slate)
- When you want to reset the warning thresholds
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_FILE = REPO_ROOT / "memory" / "session-budget.json"


def main():
    """Reset session budget to zero."""

    if SESSION_FILE.exists():
        # Show current state before reset
        try:
            data = json.loads(SESSION_FILE.read_text())
            print(f"Current state:")
            print(f"  Turn count: {data.get('turn_count', 0)}")
            print(f"  Session start: {data.get('session_start', 'unknown')}")
        except Exception:
            pass

    # Reset to zero
    data = {
        "turn_count": 0,
        "prompt_chars": 0,
        "bytes_read": 0,
        "tool_calls": 0,
        "total_tokens": 0,
        "session_start": datetime.now(timezone.utc).isoformat(),
        "reset_by": "manual",
        "reset_at": datetime.now(timezone.utc).isoformat(),
    }

    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SESSION_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(SESSION_FILE))

    print(f"\nSUCCESS: Session budget reset to 0")
    print(f"Next thresholds:")
    print(f"  - Yellow warning: 15 turns")
    print(f"  - Orange warning: 25 turns")
    print(f"  - Red auto-handoff: 35 turns")


if __name__ == "__main__":
    main()
