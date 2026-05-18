#!/bin/sh
""":"
for c in python3 py3 python py; do command -v "$c" >/dev/null 2>&1 && exec "$c" "$0" "$@"; done
for d in /c/Python* /c/Python*/Python* "/c/Program Files/Python"* "/c/Program Files/Python"*/Python* "/c/Program Files (x86)/Python"* "/c/Program Files (x86)/Python"*/Python* "$HOME/AppData/Local/Programs/Python/Python"* "$LOCALAPPDATA/Programs/Python/Python"*; do
  for n in python.exe python3.exe; do
    [ -x "$d/$n" ] && exec "$d/$n" "$0" "$@"
  done
done
echo "[HeadMaster] No python interpreter found (tried python3, py3, python, py, and common Windows install dirs)" >&2
exit 127
":"""
"""Shared inline markdown compression. Single source of truth.

Used by:
  - /compress skill (manual invocation)
  - session_end.py hook (via --consolidate-memory CLI flag)

Rules:
  - Drop filler phrases, hedging words, articles (outside code/links)
  - Preserve: YAML frontmatter, code blocks, URLs, headings, tables, paths
  - Never touch content inside backticks or fences
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_CONSOLIDATE_BYTES = 4_000

# Files that should never be compressed
NEVER_COMPRESS = {
    "PRD.md", "SYSTEM_DESIGN_NOTES.md", "JIRA_BREAKDOWN.md",
    "BRANCH_RECONCILIATION.md", "MIGRATION_PLAN.md",
}

# Filename patterns that should never be compressed
NEVER_COMPRESS_PATTERNS = [
    re.compile(r"^TDD.*\.md$"),
    re.compile(r".*_REVIEW\.md$"),
    re.compile(r"^(code-review|security-scan|qa-report|escalation|system-review).*\.md$"),
]


def compress_inline(text: str) -> str:
    # Validation: count code fences before compression
    fence_count_before = text.count("```") + text.count("~~~")

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

        # Code blocks — never touch
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        # Headings, table rows, horizontal rules, blank lines — preserve
        if (not stripped
                or stripped.startswith("#")
                or stripped.startswith("|")
                or stripped == "---"
                or stripped.startswith("- - -")):
            out.append(line)
            continue

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

        line = indent_str + re.sub(r"  +", " ", line.strip())
        out.append(line)

    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    compressed = result.strip()

    # Validation: count code fences after compression
    fence_count_after = compressed.count("```") + compressed.count("~~~")

    if fence_count_before != fence_count_after:
        # Compression corrupted code blocks — return original unchanged
        print(
            f"WARNING: compress.py: code fence mismatch "
            f"({fence_count_before} before vs {fence_count_after} after) — "
            f"compression skipped to prevent corruption",
            file=sys.stderr
        )
        return text

    return compressed


def consolidate_memory(repo_root: Path = REPO_ROOT) -> int:
    """Compress agent memory files in-place. Returns count of files compressed."""
    agents_memory = repo_root / "memory" / "agents"
    if not agents_memory.exists():
        return 0

    compressed = 0
    for md_file in agents_memory.rglob("*.md"):
        if md_file.name in NEVER_COMPRESS:
            continue
        if any(p.match(md_file.name) for p in NEVER_COMPRESS_PATTERNS):
            continue
        try:
            if md_file.stat().st_size < MIN_CONSOLIDATE_BYTES:
                continue
            raw = md_file.read_text(encoding="utf-8", errors="ignore")
            result = compress_inline(raw)
            if len(result) < len(raw) * 0.95:
                md_file.write_text(result, encoding="utf-8")
                compressed += 1
        except Exception:
            continue
    return compressed


if __name__ == "__main__":
    if "--consolidate-memory" in sys.argv:
        count = consolidate_memory()
        if count:
            log = REPO_ROOT / ".remember" / "logs" / "hook-errors.log"
            try:
                with open(log, "a", encoding="utf-8") as f:
                    f.write(f"[session_end] background compression: {count} memory file(s) compressed\n")
            except Exception:
                pass
        sys.exit(0)
    print("Usage: python compress.py --consolidate-memory", file=sys.stderr)
    sys.exit(1)
