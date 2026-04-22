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

# Default thresholds (overridden by config.yml)
DEFAULT_WARN_YELLOW = 15
DEFAULT_WARN_ORANGE = 25
DEFAULT_WARN_RED = 35


def _load_thresholds():
    """Load turn thresholds from config.yml, fall back to defaults."""
    try:
        import yaml
        config_path = REPO_ROOT / "config.yml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                budget = config.get("session_budget", {})
                return (
                    budget.get("turn_warn_yellow", DEFAULT_WARN_YELLOW),
                    budget.get("turn_warn_orange", DEFAULT_WARN_ORANGE),
                    budget.get("turn_warn_red", DEFAULT_WARN_RED),
                )
    except Exception:
        pass
    return DEFAULT_WARN_YELLOW, DEFAULT_WARN_ORANGE, DEFAULT_WARN_RED


def main() -> None:
    parts = ["HM"]

    yellow, orange, red = _load_thresholds()

    if BUDGET_FILE.exists():
        try:
            budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            turns = budget.get("turn_count", 0)
            if turns >= red:
                parts.append(f"⛔T:{turns}")
            elif turns >= orange:
                parts.append(f"🟠T:{turns}")
            elif turns >= yellow:
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
