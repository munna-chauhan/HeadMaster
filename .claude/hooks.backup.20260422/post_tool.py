#!/usr/bin/env python3
"""PostToolUse hook — handles all post-tool-use work in a single process.

Replaces deleted hooks (tool_call_tracker.py, write_compressor.py, mode_tracker.py)
with inline implementation:
  1. Increment tool_calls counter in session-budget.json
  2. Compress memory/*.md files after Write tool (opt-in, thresholds apply)
  3. Track active skill from user prompts (via env - future use)

Consolidation saves ~200ms per tool call vs spawning 3 separate processes.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_FILE = REPO_ROOT / "memory" / "session-budget.json"
FLAG_FILE = Path.home() / ".claude" / ".HeadMaster-active"
MIN_SIZE_BYTES = 4_000

# Ensure scripts module is importable
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

COMPRESSIBLE_EXTENSIONS = {".md", ".txt", ".rst"}


def _atomic_update_session(updates: dict) -> None:
    """Read-modify-write session budget with given field increments."""
    try:
        data = {}
        if SESSION_FILE.exists():
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        for k, v in updates.items():
            data[k] = data.get(k, 0) + v
        tmp = SESSION_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(str(tmp), str(SESSION_FILE))
    except Exception:
        pass


def _is_memory_md(path: Path) -> bool:
    """Only memory/**/*.md files get post-write compression."""
    from scripts.compress import NEVER_COMPRESS, NEVER_COMPRESS_PATTERNS

    if path.suffix.lower() not in COMPRESSIBLE_EXTENSIONS:
        return False
    if path.name in NEVER_COMPRESS:
        return False
    if any(p.match(path.name) for p in NEVER_COMPRESS_PATTERNS):
        return False
    try:
        return "memory" in path.resolve().parts
    except Exception:
        return False


def _compress_if_needed(path: Path) -> str | None:
    """Compress a memory file after write. Returns status message or None."""
    if not _is_memory_md(path):
        return None
    if not path.exists() or not path.is_file():
        return None
    if path.stat().st_size < MIN_SIZE_BYTES:
        return None

    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    from scripts.compress import compress_inline
    compressed = compress_inline(raw)

    raw_tokens = max(1, len(raw) // 4)
    compressed_tokens = max(1, len(compressed) // 4)
    saved_pct = round((1 - compressed_tokens / raw_tokens) * 100)

    if saved_pct < 5:
        return None

    try:
        path.write_text(compressed, encoding="utf-8")
    except Exception:
        return None

    return f"[WRITE COMPRESSED: {path.name} | {raw_tokens}→{compressed_tokens} tokens | -{saved_pct}%]"


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    # 1. Always increment tool_calls
    _atomic_update_session({"tool_calls": 1})

    # 2. Compress memory writes
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    is_write = tool_name in ("Write", "write_file")
    is_create = tool_name == "str_replace_editor" and tool_input.get("command") in ("create", "str_replace")

    compress_msg = None
    if is_write or is_create:
        file_path_str = tool_input.get("path") or tool_input.get("file_path") or tool_input.get("file", "")
        if file_path_str:
            compress_msg = _compress_if_needed(Path(file_path_str))

    if compress_msg:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": compress_msg
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
