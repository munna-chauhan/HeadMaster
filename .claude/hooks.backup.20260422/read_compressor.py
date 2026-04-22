#!/usr/bin/env python3
"""PreToolUse hook — compresses opted-in markdown reads to save tokens.

Opt-in only:
  - memory/**/*.md — session handoffs, agent working memory
  - docs/features/*/input/*.md — extracted Jira/Confluence content

Never compressed:
  - PRD.md, TDD*.md, SYSTEM_DESIGN_NOTES.md, JIRA_BREAKDOWN.md
  - *_REVIEW.md, *-review*.md, *-report*.md, *-scan*.md
  - .claude/**, config.yml, *.json
"""

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_FILE = REPO_ROOT / "memory" / "session-budget.json"
MIN_SIZE_BYTES = 4_000

# Ensure scripts module is importable
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.compress import compress_inline

COMPRESSIBLE_EXTENSIONS = {".md", ".txt", ".rst"}

COMPRESS_PATH_PATTERNS = [
    re.compile(r"[/\\]memory[/\\]"),
    re.compile(r"[/\\]input[/\\].*\.md$"),
]


def is_compressible(path: Path) -> bool:
    from scripts.compress import NEVER_COMPRESS, NEVER_COMPRESS_PATTERNS

    if path.name in NEVER_COMPRESS:
        return False
    if any(p.match(path.name) for p in NEVER_COMPRESS_PATTERNS):
        return False
    return any(p.search(str(path)) for p in COMPRESS_PATH_PATTERNS)


def _track_bytes_read(size: int) -> None:
    try:
        data = {}
        if SESSION_FILE.exists():
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        data["bytes_read"] = data.get("bytes_read", 0) + size
        tmp = SESSION_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(str(tmp), str(SESSION_FILE))
    except Exception:
        pass


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    is_read = tool_name in ("Read", "read_file")
    is_view = tool_name == "str_replace_editor" and tool_input.get("command") == "view"
    if not is_read and not is_view:
        sys.exit(0)

    file_path_str = tool_input.get("path") or tool_input.get("file_path") or tool_input.get("file", "")
    if not file_path_str:
        sys.exit(0)

    path = Path(file_path_str)
    if path.suffix.lower() not in COMPRESSIBLE_EXTENSIONS:
        sys.exit(0)
    if not is_compressible(path):
        sys.exit(0)
    if not path.exists() or not path.is_file():
        sys.exit(0)

    size = path.stat().st_size
    _track_bytes_read(size)

    if size < MIN_SIZE_BYTES:
        sys.exit(0)

    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        sys.exit(0)

    compressed = compress_inline(raw)
    raw_tokens = max(1, len(raw) // 4)
    compressed_tokens = max(1, len(compressed) // 4)
    saved_pct = round((1 - compressed_tokens / raw_tokens) * 100)

    if saved_pct < 5:
        sys.exit(0)

    print(json.dumps({
        "decision": "block",
        "reason": f"Compressed {path.name}: {raw_tokens}→{compressed_tokens} tokens (-{saved_pct}%)",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"[COMPRESSED READ: {path.name} | {raw_tokens}→{compressed_tokens} tokens | -{saved_pct}%]\n\n"
                f"{compressed}\n\n"
                f"[END: {path.name}]"
            )
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
