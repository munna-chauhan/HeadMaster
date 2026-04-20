#!/usr/bin/env python3
"""Statusline hook — shows active skill mode + token budget indicator."""
import json
from datetime import datetime, timezone
from pathlib import Path

FLAG_FILE = Path.home() / ".claude" / ".HeadMaster-active"
BUDGET_FILE = Path.home() / ".claude" / ".HeadMaster-session-budget.json"
STALE_SECONDS = 3600

WARN_YELLOW = 15
WARN_ORANGE = 25
WARN_RED = 35


def main() -> None:
    badge_parts = []

    # Skill + model from flag file
    if FLAG_FILE.exists():
        try:
            data = json.loads(FLAG_FILE.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(data["timestamp"])
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age <= STALE_SECONDS:
                skill = data.get("skill", "").upper()
                model = data.get("model", "")
                model_short = ""
                if model:
                    for part in ["opus", "sonnet", "haiku"]:
                        if part in model.lower():
                            model_short = part
                            break
                if skill:
                    badge_parts.append(f"HM:{skill}")
                if model_short:
                    badge_parts.append(model_short)
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    # Turn count indicator
    if BUDGET_FILE.exists():
        try:
            budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            turns = budget.get("turn_count", 0)
            if turns >= WARN_RED:
                badge_parts.append(f"⛔T:{turns}")
            elif turns >= WARN_ORANGE:
                badge_parts.append(f"🟠T:{turns}")
            elif turns >= WARN_YELLOW:
                badge_parts.append(f"🟡T:{turns}")
            elif turns > 0:
                badge_parts.append(f"T:{turns}")
        except (json.JSONDecodeError, Exception):
            pass

    # Hook error indicator — check if errors logged this session
    error_log = Path.home() / ".claude" / ".HeadMaster-hook-errors.log"
    if error_log.exists() and BUDGET_FILE.exists():
        try:
            budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            session_start = budget.get("session_start", "")
            if session_start:
                # Check if any error line timestamp is >= session_start
                for line in error_log.read_text(encoding="utf-8").splitlines()[-5:]:
                    if line[:19] >= session_start[:19]:
                        badge_parts.append("⚠️")
                        break
        except Exception:
            pass

    if badge_parts:
        print(f"[{' | '.join(badge_parts)}]")


if __name__ == "__main__":
    main()
