#!/usr/bin/env python
"""Parse verdict from a review/QA report markdown file.

Usage:
    python scripts/parse_verdict.py <file.md> <valid_verdicts>

Arguments:
    file.md          Path to the review report markdown file
    valid_verdicts   Comma-separated list of valid verdict keywords (case-insensitive)

Exit codes:
    0  Verdict found and valid
    1  No '## Verdict' section found (or section exists but verdict not on immediate next line)
    2  Verdict keyword found but not in valid list
    3  File not found

Stdout:
    The normalized (uppercased) verdict keyword on exit 0

Stderr:
    Error messages and warnings
"""

import re
import sys
from pathlib import Path


def parse_verdict(content: str, valid_verdicts: list[str]) -> tuple[int, str, str]:
    """Parse verdict from report content.

    Returns:
        (exit_code, verdict_or_empty, error_or_warning)
    """
    lines = content.splitlines()

    # Look for new-format ## Verdict section
    verdict_section_idx = None
    for i, line in enumerate(lines):
        if re.match(r'^##\s+Verdict\s*$', line.strip()):
            verdict_section_idx = i
            break

    if verdict_section_idx is not None:
        # Verdict must be on the immediately following non-blank line
        verdict_line = None
        for j in range(verdict_section_idx + 1, len(lines)):
            stripped = lines[j].strip()
            if stripped:
                verdict_line = stripped
                break

        if verdict_line is None:
            return 1, "", "No '## Verdict' section found (section present but empty)"

        # Validate the verdict is a single keyword (no inline prose)
        # The verdict line must be exactly a keyword with no surrounding text
        if not re.match(r'^[A-Z_a-z\-]+$', verdict_line):
            return 1, "", f"No '## Verdict' section found (verdict line malformed: '{verdict_line}')"

        normalized = verdict_line.upper()

        # Check if there are sections after the verdict
        post_sections = [l for l in lines[verdict_section_idx + 1:] if re.match(r'^##\s+', l)]
        warning = ""
        if post_sections:
            warning = f"WARNING: Content found after verdict section: {post_sections[0].strip()}"

        valid_upper = [v.upper() for v in valid_verdicts]
        if normalized not in valid_upper:
            return 2, "", f"Invalid verdict '{normalized}'. Valid: {', '.join(valid_upper)}"

        return 0, normalized, warning

    # Fallback: look for old-format "Verdict: KEYWORD" in prose
    old_format_pattern = re.compile(r'^Verdict:\s+([A-Z_a-z\-]+)', re.MULTILINE)
    match = old_format_pattern.search(content)
    if match:
        normalized = match.group(1).upper()
        valid_upper = [v.upper() for v in valid_verdicts]
        if normalized not in valid_upper:
            return 2, "", f"Invalid verdict '{normalized}'. Valid: {', '.join(valid_upper)}"
        return 0, normalized, "Old verdict format detected — consider updating to '## Verdict' section"

    return 1, "", "No '## Verdict' section found"


def main():
    if len(sys.argv) < 3:
        print("Usage: parse_verdict.py <file.md> <valid_verdicts>", file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    valid_verdicts_raw = sys.argv[2]
    valid_verdicts = [v.strip() for v in valid_verdicts_raw.split(",") if v.strip()]

    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(3)

    content = file_path.read_text(encoding="utf-8")

    exit_code, verdict, message = parse_verdict(content, valid_verdicts)

    if message:
        print(message, file=sys.stderr)

    if exit_code == 0:
        print(verdict)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
