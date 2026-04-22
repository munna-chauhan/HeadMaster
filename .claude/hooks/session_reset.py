#!/usr/bin/env python3
"""SessionStart hook — resets token budget counter for new session."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_FILE = REPO_ROOT / "memory" / "session-budget.json"


def main() -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data (don't reset turn_count across sessions)
    existing_data = {}
    if SESSION_FILE.exists():
        try:
            existing_data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Keep turn_count, reset per-session metrics
    data = {
        "turn_count": existing_data.get("turn_count", 0),  # PRESERVE across sessions
        "prompt_chars": 0,  # Reset per session
        "bytes_read": 0,    # Reset per session
        "tool_calls": 0,    # Reset per session
        "total_tokens": existing_data.get("turn_count", 0),  # Same as turn_count
        "session_start": datetime.now(timezone.utc).isoformat(),
        "last_reset": datetime.now(timezone.utc).isoformat(),
    }
    tmp = SESSION_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(str(tmp), str(SESSION_FILE))


if __name__ == "__main__":
    main()
