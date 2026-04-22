#!/usr/bin/env python3
"""Statusline hook — shows session health in status bar.

Format: [HM | T:12] or [HM | 🟠T:26] or [HM | ⛔T:36]
Adds ⚠️ if hook errors detected this session.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_FILE = REPO_ROOT / "memory" / "session-budget.json"

WARN_YELLOW = 15
WARN_ORANGE = 25
WARN_RED = 35


def main() -> None:
    parts = ["HM"]

    if BUDGET_FILE.exists():
        try:
            budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            turns = budget.get("turn_count", 0)
            if turns >= WARN_RED:
                parts.append(f"⛔T:{turns}")
            elif turns >= WARN_ORANGE:
                parts.append(f"🟠T:{turns}")
            elif turns >= WARN_YELLOW:
                parts.append(f"🟡T:{turns}")
            elif turns > 0:
                parts.append(f"T:{turns}")
        except Exception:
            pass

    # Hook error indicator
    error_log = Path.home() / "memory" / "hook-errors.log"
    if error_log.exists() and BUDGET_FILE.exists():
        try:
            budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            session_start = budget.get("session_start", "")
            if session_start:
                for line in error_log.read_text(encoding="utf-8").splitlines()[-5:]:
                    if line[:19] >= session_start[:19]:
                        parts.append("⚠️")
                        break
        except Exception:
            pass

    if len(parts) > 1:
        print(f"[{' | '.join(parts)}]")


if __name__ == "__main__":
    main()
