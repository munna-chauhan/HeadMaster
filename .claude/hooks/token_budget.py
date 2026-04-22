#!/usr/bin/env python3
"""
UserPromptSubmit hook — tracks session age via turn count (the only reliable signal).

Claude Code does NOT expose actual token counts. Rather than pretending with
inaccurate formulas, we use turn count as the primary signal and bytes_read
as a secondary signal (large file reads are observable cost).

Thresholds are turn-based:
  - 🟡 at 15 turns
  - 🟠 at 25 turns
  - ⛔ at 35 turns

If bytes_read > 500KB, downgrade thresholds by 5 turns each (heavy read sessions
consume context faster).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = REPO_ROOT / "memory"
SESSION_FILE = MEMORY_DIR / "session-budget.json"

# Default turn-based thresholds (overridable in config.yml)
DEFAULT_WARN_YELLOW = 15
DEFAULT_WARN_ORANGE = 25
DEFAULT_WARN_RED = 35

# Heavy-read downgrade: if bytes_read > this, subtract 5 from each threshold
HEAVY_READ_THRESHOLD = 512_000  # 500KB


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


def load_session() -> dict:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            try:
                from datetime import datetime as _dt
                _log = Path.home() / "memory" / "hook-errors.log"
                with open(_log, "a") as _f:
                    _f.write(f"{_dt.now().isoformat()} {Path(__file__).name}: {type(e).__name__}: {e}\n")
            except Exception:
                pass
    return {
        "turn_count": 0,
        "prompt_chars": 0,
        "bytes_read": 0,
        "tool_calls": 0,
        "total_tokens": 0,
        "session_start": datetime.now(timezone.utc).isoformat(),
    }


def save_session(data: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SESSION_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(str(tmp), str(SESSION_FILE))


def write_auto_handoff(turns: int) -> None:
    try:
        flag_file = Path.home() / ".claude" / ".HeadMaster-active"
        slug = "unknown"
        if flag_file.exists():
            try:
                flag = json.loads(flag_file.read_text(encoding="utf-8"))
                slug = flag.get("slug", "unknown")
            except Exception:
                pass

        memory_dir = REPO_ROOT / "memory" / "features" / slug
        memory_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        handoff_path = memory_dir / f"session-{ts}-auto.md"
        content = f"""# Auto-Handoff: Session Age Exceeded

**Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC
**Reason:** Session age exceeded ({turns} turns)
**Feature:** {slug}

## Next Session
1. `claude --name "{slug}"`
2. `/navigate {slug}` — detects phase from artifacts, resumes from last gate
"""
        handoff_path.write_text(content, encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    payload = {}
    try:
        if not sys.stdin.isatty():
            payload = json.loads(sys.stdin.read())
    except Exception:
        pass

    # Extract user prompt text
    prompt = payload.get("prompt", "")
    if not prompt and len(sys.argv) > 1:
        prompt = sys.argv[1]

    prompt_chars = len(prompt) if prompt else 0
    if prompt_chars == 0:
        sys.exit(0)

    session = load_session()
    session["turn_count"] += 1
    session["prompt_chars"] += prompt_chars
    # bytes_read and tool_calls are updated by read_compressor and PostToolUse hook

    turns = session["turn_count"]
    # Keep total_tokens for backward compat with metrics.py
    session["total_tokens"] = turns
    save_session(session)

    # Load thresholds from config
    yellow, orange, red = _load_thresholds()

    # Adjust thresholds if heavy reads
    if session["bytes_read"] > HEAVY_READ_THRESHOLD:
        yellow -= 5
        orange -= 5
        red -= 5

    if turns < yellow:
        sys.exit(0)

    reads_kb = session["bytes_read"] // 1024
    bar_filled = min(20, int(20 * turns / red))
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    breakdown = f"reads:{reads_kb}KB tools:{session['tool_calls']}"

    if turns >= red:
        write_auto_handoff(turns)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"""
⛔ SESSION AGE EXCEEDED — {turns} turns ({breakdown})
[{bar}] {turns} / {red} turns

Auto-handoff written to memory/. Run /handoff then start new session.
"""
            }
        }
    elif turns >= orange:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"""
🟠 SESSION AGE WARNING — {turns} turns ({breakdown})
[{bar}] {turns} / {red} turns

Approaching limit. Run /handoff soon.
"""
            }
        }
    else:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"""
🟡 SESSION AGE NOTICE — {turns} turns ({breakdown})
[{bar}] {turns} / {red} turns
"""
            }
        }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
