#!/usr/bin/env python3
"""
PreToolUse hook — intercepts Read tool calls on large markdown files.

When Claude tries to read a .md file above the size threshold:
1. Reads the file directly
2. Compresses it inline (drop articles, filler, hedging)
3. Blocks the original Read call
4. Injects compressed content as additionalContext

Claude gets the compressed content without ever loading the raw file.

Thresholds:
  < MIN_SIZE_BYTES  → allow raw read (small files, not worth compressing)
  >= MIN_SIZE_BYTES → compress and serve inline

Never compresses:
  - Formal artifacts: PRD.md, TDD*.md, SYSTEM_DESIGN_NOTES.md, JIRA_BREAKDOWN.md, *_REVIEW.md
  - Code files: .py, .js, .ts, .java, .yml, .yaml, .json
  - Binary files
  - Files outside the repo
"""

import json
import re
import sys
from pathlib import Path

# Only compress files larger than this
MIN_SIZE_BYTES = 8_000  # ~2k tokens

# Formal artifacts — never compress, always read raw
NEVER_COMPRESS = {
    "PRD.md", "SYSTEM_DESIGN_NOTES.md", "JIRA_BREAKDOWN.md",
    "MIGRATION_PLAN.md", "FEATURE_INPUT.md",
}
NEVER_COMPRESS_PATTERNS = [
    re.compile(r"TDD.*\.md$"),
    re.compile(r".*_REVIEW\.md$"),
    re.compile(r".*\.original\.md$"),
]

# Only compress these extensions
COMPRESSIBLE_EXTENSIONS = {".md", ".txt", ".rst"}


def is_protected(path: Path) -> bool:
    """Return True if file should never be compressed."""
    name = path.name
    if name in NEVER_COMPRESS:
        return True
    return any(p.match(name) for p in NEVER_COMPRESS_PATTERNS)


def compress_inline(text: str) -> str:
    """
    Fast inline compression — no API call, pure regex.
    Drops filler words, hedging, verbose phrases.
    Preserves: code blocks, URLs, headings, tables, paths.
    """
    lines = text.split("\n")
    out = []
    in_code = False

    for line in lines:
        # Track code blocks — never touch these
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        # Preserve headings, table rows, blank lines as-is
        if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("---"):
            out.append(line)
            continue

        # Capture original indentation before any modification
        original_indent = len(line) - len(line.lstrip())
        indent_str = line[:original_indent]

        # Drop filler phrases (whole phrases first)
        line = re.sub(
            r"\b(in order to|please note that|it is important to note|"
            r"it should be noted that|as mentioned above|as noted above|"
            r"it is worth noting that|needless to say|"
            r"at the end of the day|for all intents and purposes)\b",
            "", line, flags=re.IGNORECASE
        )

        # Drop hedging
        line = re.sub(
            r"\b(just|really|basically|actually|essentially|generally|"
            r"typically|usually|normally|certainly|definitely|absolutely|"
            r"obviously|clearly|simply|merely|quite|rather|somewhat|"
            r"arguably|potentially|possibly|perhaps|maybe|might want to|"
            r"you may want to|you might want to|feel free to)\b",
            "", line, flags=re.IGNORECASE
        )

        # Drop articles only when safe (not inside code-like content)
        if not re.search(r"[`\[\(]", line):
            line = re.sub(r"\b(a |an |the )", " ", line)

        # Collapse multiple spaces, strip, then restore original indentation
        line = indent_str + re.sub(r"  +", " ", line.strip())

        out.append(line)

    result = "\n".join(out)
    # Collapse 3+ blank lines to 2
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def main() -> None:
    # Read hook event from stdin
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    # Only intercept Read tool
    if tool_name not in ("Read", "read_file"):
        sys.exit(0)

    file_path_str = tool_input.get("file_path", tool_input.get("path", ""))
    if not file_path_str:
        sys.exit(0)

    path = Path(file_path_str)

    # Only compress compressible extensions
    if path.suffix.lower() not in COMPRESSIBLE_EXTENSIONS:
        sys.exit(0)

    # Never compress protected artifacts
    if is_protected(path):
        sys.exit(0)

    # File must exist and be above threshold
    if not path.exists() or not path.is_file():
        sys.exit(0)

    size = path.stat().st_size
    if size < MIN_SIZE_BYTES:
        sys.exit(0)

    # Read and compress
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        sys.exit(0)

    compressed = compress_inline(raw)

    raw_tokens = max(1, len(raw) // 4)
    compressed_tokens = max(1, len(compressed) // 4)
    saved_pct = round((1 - compressed_tokens / raw_tokens) * 100)

    # Block the raw read, serve compressed content instead
    output = {
        "decision": "block",
        "reason": f"Serving compressed version of {path.name} ({raw_tokens}->{compressed_tokens} tokens, -{saved_pct}%)",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": f"[COMPRESSED READ: {path} | {raw_tokens}→{compressed_tokens} tokens | -{saved_pct}%]\n\n{compressed}\n\n[END: {path.name}]"
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
