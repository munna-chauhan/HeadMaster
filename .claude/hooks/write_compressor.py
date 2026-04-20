#!/usr/bin/env python3
"""
PostToolUse hook — compresses ONLY working memory files after Claude writes them.

Uses an ALLOWLIST model: only files matching explicit patterns get compressed.
Everything else passes through untouched. This prevents silent corruption of
formal artifacts (SYSTEM_DESIGN_NOTES.md, JIRA_BREAKDOWN.md, review reports, etc.).

Allowlist (files safe to compress):
  - memory/**/*.md          — agent memory, session notes, decisions

All other files are formal artifacts or execution state and must not be modified.
"""

import json
import re
import sys
from pathlib import Path

MIN_SIZE_BYTES = 4_000

# ALLOWLIST: only these files get compressed. Everything else is untouched.
# NOTE: FEATURE_DRAFT.md and DISCOVERY_NOTES.md intentionally excluded —
# they carry semantic hedging words (typically, generally, might) that
# compression destroys, converting soft constraints into hard requirements.
ALLOW_COMPRESS_NAMES = set()

COMPRESSIBLE_EXTENSIONS = {".md", ".txt", ".rst"}

# Explicit NEVER compress — even if path matches allowlist patterns
NEVER_COMPRESS = {
    "PRD.md",
    "SYSTEM_DESIGN_NOTES.md",
    "JIRA_BREAKDOWN.md",
    "BRANCH_RECONCILIATION.md",
    "MIGRATION_PLAN.md",
}
NEVER_COMPRESS_PATTERNS = [
    re.compile(r"^TDD.*\.md$"),
    re.compile(r".*_REVIEW\.md$"),
    re.compile(r"^(code-review|security-scan|qa-report|escalation|system-review).*\.md$"),
]


def is_compressible(path: Path) -> bool:
    """Return True only if this file is explicitly allowed for compression."""
    if path.suffix.lower() not in COMPRESSIBLE_EXTENSIONS:
        return False

    # Check NEVER_COMPRESS first
    if path.name in NEVER_COMPRESS:
        return False
    if any(p.match(path.name) for p in NEVER_COMPRESS_PATTERNS):
        return False

    # Allow: memory/**/*.md (agent memory, session notes)
    try:
        parts = path.resolve().parts
        if "memory" in parts:
            return True
    except Exception as e:
        try:
            from datetime import datetime as _dt
            _log = Path.home() / ".claude" / ".HeadMaster-hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} {Path(__file__).name}: {type(e).__name__}: {e}\n")
        except Exception:
            pass

    # Allow: specific working file names
    if path.name in ALLOW_COMPRESS_NAMES:
        return True

    return False


def compress_inline(text: str) -> str:
    """
    Inline compression — pure regex, no API call.
    Drops filler, hedging, articles.
    Preserves: YAML frontmatter, code blocks, URLs, headings, tables, paths.
    """
    lines = text.split("\n")
    out = []
    in_code = False
    in_frontmatter = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # YAML frontmatter — preserve exactly
        if i == 0 and stripped == "---":
            in_frontmatter = True
            out.append(line)
            continue
        if in_frontmatter:
            out.append(line)
            if stripped == "---" and i > 0:
                in_frontmatter = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        if (not stripped
                or stripped.startswith("#")
                or stripped.startswith("|")
                or stripped == "---"
                or stripped.startswith("- - -")):
            out.append(line)
            continue

        original_indent = len(line) - len(line.lstrip())
        indent_str = line[:original_indent]

        line = re.sub(
            r"\b(in order to|please note that|it is important to note|"
            r"it should be noted that|as mentioned above|as noted above|"
            r"it is worth noting that|needless to say|"
            r"at the end of the day|for all intents and purposes)\b",
            "", line, flags=re.IGNORECASE
        )
        line = re.sub(
            r"\b(just|really|basically|actually|essentially|generally|"
            r"typically|usually|normally|certainly|definitely|absolutely|"
            r"obviously|clearly|simply|merely|quite|rather|somewhat|"
            r"arguably|potentially|possibly|perhaps|maybe|might want to|"
            r"you may want to|you might want to|feel free to)\b",
            "", line, flags=re.IGNORECASE
        )
        if not re.search(r"[`\[\(]", line):
            line = re.sub(r"\b(a |an |the )", " ", line)

        line = indent_str + re.sub(r"  +", " ", line.strip())
        out.append(line)

    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception as e:
        try:
            from datetime import datetime as _dt
            _log = Path.home() / ".claude" / ".HeadMaster-hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} {Path(__file__).name}: {type(e).__name__}: {e}\n")
        except Exception:
            pass
        sys.exit(0)

    tool_name  = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    is_write = tool_name in ("Write", "write_file")
    is_create = (tool_name == "str_replace_editor"
                 and tool_input.get("command") in ("create", "str_replace"))

    if not is_write and not is_create:
        sys.exit(0)

    file_path_str = (tool_input.get("path")
                     or tool_input.get("file_path")
                     or tool_input.get("file", ""))
    if not file_path_str:
        sys.exit(0)

    path = Path(file_path_str)

    if not is_compressible(path):
        sys.exit(0)

    if not path.exists() or not path.is_file():
        sys.exit(0)

    size = path.stat().st_size
    if size < MIN_SIZE_BYTES:
        sys.exit(0)

    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        try:
            from datetime import datetime as _dt
            _log = Path.home() / ".claude" / ".HeadMaster-hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} {Path(__file__).name}: {type(e).__name__}: {e}\n")
        except Exception:
            pass
        sys.exit(0)

    compressed = compress_inline(raw)

    raw_tokens        = max(1, len(raw) // 4)
    compressed_tokens = max(1, len(compressed) // 4)
    saved_pct         = round((1 - compressed_tokens / raw_tokens) * 100)

    if saved_pct < 5:
        sys.exit(0)

    try:
        path.write_text(compressed, encoding="utf-8")
    except Exception as e:
        try:
            from datetime import datetime as _dt
            _log = Path.home() / ".claude" / ".HeadMaster-hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} {Path(__file__).name}: {type(e).__name__}: {e}\n")
        except Exception:
            pass
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[WRITE COMPRESSED: {path.name} | {raw_tokens}→{compressed_tokens} tokens | -{saved_pct}%]"
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
