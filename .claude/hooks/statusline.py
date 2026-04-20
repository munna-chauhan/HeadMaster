#!/usr/bin/env python3
"""Statusline hook — shows active skill mode + token budget indicator."""
import json
from datetime import datetime, timezone
from pathlib import Path

FLAG_FILE = Path.home() / ".claude" / ".HeadMaster-active"
BUDGET_FILE = Path.home() / ".claude" / ".HeadMaster-session-budget.json"
STALE_SECONDS = 3600

WARN_YELLOW = 50_000
WARN_ORANGE = 100_000
WARN_RED = 150_000


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


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

    # Token budget indicator
    if BUDGET_FILE.exists():
        try:
            budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            total = budget.get("total_tokens", 0)
            if total >= WARN_RED:
                badge_parts.append(f"⛔{format_tokens(total)}")
            elif total >= WARN_ORANGE:
                badge_parts.append(f"🟠{format_tokens(total)}")
            elif total >= WARN_YELLOW:
                badge_parts.append(f"🟡{format_tokens(total)}")
        except (json.JSONDecodeError, Exception):
            pass

    if badge_parts:
        print(f"[{' | '.join(badge_parts)}]")


if __name__ == "__main__":
    main()
