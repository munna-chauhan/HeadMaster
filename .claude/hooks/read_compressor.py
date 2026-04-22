#!/usr/bin/env python3
"""
PreToolUse hook — intercepts Read tool calls on markdown files.

OPT-IN compression model: only compresses files in explicitly allowed
categories (working memory, extracted input). Everything else passes
through unmodified.

Compressible (opt-in):
  - memory/**/*.md         — session handoffs, agent working memory
  - docs/features/*/input/*.md — extracted Jira/Confluence content

Never compressed (everything else):
  - .claude/agents/*.md    — agent behavioral definitions
  - .claude/skills/**      — skill orchestration logic
  - .claude/commands/*.md  — command definitions
  - .claude/workflows/*    — workflow definitions
  - CLAUDE.md              — system instructions
  - PRD.md, TDD*.md        — formal specs
  - SYSTEM_DESIGN_NOTES.md — architecture (immutable ADRs)
  - JIRA_BREAKDOWN.md      — story definitions + execution state
  - *_REVIEW.md            — review artifacts
  - *-review*.md, *-report*.md, *-scan*.md — execution reports
  - config.yml, *.json     — configuration
  - All other files        — default is DO NOT compress

Thresholds:
  < MIN_SIZE_BYTES  → allow raw read (not worth compressing)
  >= MIN_SIZE_BYTES → compress and serve inline

YAML frontmatter (between opening --- and closing ---) is always
preserved exactly — hook prompts and metadata must not be altered.
"""

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_FILE = REPO_ROOT / "memory" / "session-budget.json"

MIN_SIZE_BYTES = 4_000  # ~1k tokens — lower threshold to catch more files

COMPRESSIBLE_EXTENSIONS = {".md", ".txt", ".rst"}

# Paths that OPT-IN to compression (only these get compressed)
COMPRESS_PATH_PATTERNS = [
    re.compile(r"[/\\]memory[/\\]"),              # memory/**/*
    re.compile(r"[/\\]input[/\\].*\.md$"),        # docs/features/*/input/*.md
]

# Explicit NEVER compress — even if path matches opt-in patterns
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
    """Return True only if file is in an explicitly opted-in category."""
    # Check NEVER_COMPRESS first
    if path.name in NEVER_COMPRESS:
        return False
    if any(p.match(path.name) for p in NEVER_COMPRESS_PATTERNS):
        return False

    path_str = str(path)
    return any(p.search(path_str) for p in COMPRESS_PATH_PATTERNS)


def compress_inline(text: str) -> str:
    """
    Inline compression for working memory files only.
    Drops filler, hedging, articles.
    Preserves: YAML frontmatter, code blocks, URLs, headings, tables, paths.
    """
    lines = text.split("\n")
    out = []
    in_code = False
    in_frontmatter = False
    frontmatter_done = False

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
                frontmatter_done = True
            continue

        # Code blocks — never touch
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        # Headings, table rows, horizontal rules, blank lines — preserve as-is
        if (not stripped
                or stripped.startswith("#")
                or stripped.startswith("|")
                or stripped == "---"
                or stripped.startswith("- - -")):
            out.append(line)
            continue

        # Capture indentation before modifying
        original_indent = len(line) - len(line.lstrip())
        indent_str = line[:original_indent]

        # Drop filler phrases
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
        # Drop articles only when no code-like content on line
        if not re.search(r"[`\[\(]", line):
            line = re.sub(r"\b(a |an |the )", " ", line)

        # Restore indentation
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

    # Handle both Read tool and str_replace_editor view command
    is_read = tool_name in ("Read", "read_file")
    is_view = (tool_name == "str_replace_editor"
               and tool_input.get("command") == "view")

    if not is_read and not is_view:
        sys.exit(0)

    file_path_str = (tool_input.get("path")
                     or tool_input.get("file_path")
                     or tool_input.get("file", ""))
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

    # Track bytes read for token budget cost model (always, even if not compressed)
    _track_bytes_read(size)

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

    # Not worth blocking if savings are negligible
    if saved_pct < 5:
        sys.exit(0)

    output = {
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
    }

    print(json.dumps(output))
    sys.exit(0)


def _track_bytes_read(size: int) -> None:
    """Atomically increment bytes_read in the session budget file."""
    try:
        data = {}
        if SESSION_FILE.exists():
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        data["bytes_read"] = data.get("bytes_read", 0) + size
        tmp = SESSION_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(str(tmp), str(SESSION_FILE))
    except Exception as e:
        try:
            from datetime import datetime as _dt
            _log = Path.home() / ".claude" / ".HeadMaster-hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} {Path(__file__).name}: {type(e).__name__}: {e}\n")
        except Exception:
            pass  # truly best-effort


if __name__ == "__main__":
    main()
