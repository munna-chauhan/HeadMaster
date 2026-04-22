#!/usr/bin/env python3
"""Shared inline markdown compression. Single source of truth.

Used by:
  - .claude/hooks/read_compressor.py (PreToolUse — compress on read)
  - .claude/hooks/post_tool.py (PostToolUse — compress memory writes)
  - /compress skill (manual invocation)

Rules:
  - Drop filler phrases, hedging words, articles (outside code/links)
  - Preserve: YAML frontmatter, code blocks, URLs, headings, tables, paths
  - Never touch content inside backticks or fences
"""

import re


def compress_inline(text: str) -> str:
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
    return result.strip()
