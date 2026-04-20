#!/usr/bin/env python3
"""
PostToolUse hook — increments tool_calls counter in session budget.

Each tool call adds overhead to the context window (tool input + result).
This gives the cost model an exact count of tool invocations.
"""

import json
import os
import sys
from pathlib import Path

SESSION_FILE = Path.home() / ".claude" / ".HeadMaster-session-budget.json"


def main() -> None:
    try:
        data = {}
        if SESSION_FILE.exists():
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        data["tool_calls"] = data.get("tool_calls", 0) + 1
        tmp = SESSION_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(str(tmp), str(SESSION_FILE))
    except Exception as e:
        try:
            from pathlib import Path as _P
            from datetime import datetime as _dt
            _log = _P.home() / ".claude" / ".HeadMaster-hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} {Path(__file__).name}: {type(e).__name__}: {e}\n")
        except Exception:
            pass  # truly best-effort
    sys.exit(0)


if __name__ == "__main__":
    main()
