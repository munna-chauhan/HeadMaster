#!/usr/bin/env python3
"""SessionStart hook — resets token budget counter for new session."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

SESSION_FILE = Path.home() / ".claude" / ".HeadMaster-session-budget.json"


def main() -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "total_tokens": 0,
        "turn_count": 0,
        "session_start": datetime.now(timezone.utc).isoformat(),
    }
    tmp = SESSION_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(str(tmp), str(SESSION_FILE))


if __name__ == "__main__":
    main()
