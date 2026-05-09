#!/usr/bin/env python
"""
Diff-based review filter for incremental document reviews.

Extracts changed sections from markdown files using git diff to enable targeted
reviews instead of re-reviewing entire documents. Reduces token consumption for
small changes to approved PRDs/TDDs.

Usage:
    python scripts/diff_review_filter.py <file_path> [--context-sections <n>]

Returns:
    - Changed sections with surrounding context
    - Section headers for navigation
    - Diff summary (lines added/removed)

Exit codes:
    0 - Changes detected, filtered content returned
    1 - No changes detected (new file or no diff)
    2 - Error (file not found, git error)
"""

import sys
import subprocess
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Set


def get_git_diff(file_path: str) -> Tuple[str, bool]:
    """
    Get git diff for file. Returns (diff_output, is_new_file).

    For new files (not in git yet), returns empty diff and is_new_file=True.
    """
    try:
        # Check if file is tracked
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", file_path],
            capture_output=True,
            text=True,
            cwd=Path(file_path).parent
        )

        if result.returncode != 0:
            # File not tracked - treat as new
            return "", True

        # Get diff against HEAD
        result = subprocess.run(
            ["git", "diff", "HEAD", file_path],
            capture_output=True,
            text=True,
            cwd=Path(file_path).parent
        )

        if result.returncode != 0:
            print(f"Error: git diff failed: {result.stderr}", file=sys.stderr)
            sys.exit(2)

        return result.stdout, False

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


def parse_diff_hunks(diff_output: str) -> List[Tuple[int, int]]:
    """
    Parse git diff output to extract changed line ranges.
    Returns list of (start_line, end_line) tuples.
    """
    hunks = []
    hunk_pattern = re.compile(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')

    for match in hunk_pattern.finditer(diff_output):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) else 1
        end = start + count - 1
        hunks.append((start, end))

    return hunks


def extract_section_headers(content: str) -> List[Tuple[str, int, int]]:
    """
    Extract markdown section headers with their line ranges.
    Returns list of (header_text, start_line, level).
    """
    sections = []
    lines = content.split('\n')

    for i, line in enumerate(lines, 1):
        # Match markdown headers (# Header or ## Header etc)
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            header = match.group(2).strip()
            sections.append((header, i, level))

    return sections


def find_containing_sections(line_num: int, sections: List[Tuple[str, int, int]]) -> List[str]:
    """
    Find all section headers that contain the given line number.
    Returns list of section headers from top-level to immediate parent.
    """
    containing = []
    current_sections = [None] * 7  # Max 6 levels + placeholder

    for header, start_line, level in sections:
        if start_line <= line_num:
            current_sections[level] = header
            # Clear deeper levels
            for i in range(level + 1, 7):
                current_sections[i] = None
        elif start_line > line_num:
            break

    # Collect non-None sections
    containing = [s for s in current_sections if s]
    return containing


def get_section_range(sections: List[Tuple[str, int, int]], section_idx: int, total_lines: int) -> Tuple[int, int]:
    """
    Get line range for a section (from section start to next section of same/higher level).
    """
    _, start_line, level = sections[section_idx]

    # Find next section at same or higher level
    end_line = total_lines
    for i in range(section_idx + 1, len(sections)):
        _, next_start, next_level = sections[i]
        if next_level <= level:
            end_line = next_start - 1
            break

    return start_line, end_line


def extract_changed_sections(file_path: str, context_sections: int = 0) -> str:
    """
    Extract changed sections from markdown file based on git diff.

    Args:
        file_path: Path to markdown file
        context_sections: Number of sibling sections to include as context (0 = changed sections only)

    Returns:
        Filtered markdown content with only changed sections + context
    """
    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(2)

    total_lines = len(content.split('\n'))

    # Get git diff
    diff_output, is_new_file = get_git_diff(file_path)

    if is_new_file or not diff_output.strip():
        # No diff - return empty (caller should do full review)
        return ""

    # Parse diff hunks
    changed_ranges = parse_diff_hunks(diff_output)
    if not changed_ranges:
        return ""

    # Extract section structure
    sections = extract_section_headers(content)
    if not sections:
        # No sections - return full content (edge case)
        return content

    # Find all sections that contain changes
    changed_section_indices: Set[int] = set()

    for start, end in changed_ranges:
        for line_num in range(start, end + 1):
            # Find which section this line belongs to
            for idx, (header, section_start, level) in enumerate(sections):
                section_end = total_lines
                if idx + 1 < len(sections):
                    section_end = sections[idx + 1][1] - 1

                if section_start <= line_num <= section_end:
                    changed_section_indices.add(idx)
                    break

    # Add context sections (siblings)
    if context_sections > 0:
        expanded_indices = set(changed_section_indices)
        for idx in changed_section_indices:
            _, _, level = sections[idx]
            # Add siblings at same level
            for i in range(max(0, idx - context_sections), min(len(sections), idx + context_sections + 1)):
                if sections[i][2] == level:
                    expanded_indices.add(i)
        changed_section_indices = expanded_indices

    # Extract changed section content
    lines = content.split('\n')
    output_lines = []
    included_ranges: List[Tuple[int, int]] = []

    for idx in sorted(changed_section_indices):
        start, end = get_section_range(sections, idx, total_lines)
        included_ranges.append((start, end))
        output_lines.extend(lines[start-1:end])

    # Generate summary
    summary = f"# INCREMENTAL REVIEW SCOPE\n\n"
    summary += f"**File:** {Path(file_path).name}\n"
    summary += f"**Changed sections:** {len(changed_section_indices)}\n"
    summary += f"**Total sections in document:** {len(sections)}\n\n"
    summary += "## Changed Sections:\n\n"

    for idx in sorted(changed_section_indices):
        header, start_line, level = sections[idx]
        indent = "  " * (level - 1)
        summary += f"{indent}- {header} (line {start_line})\n"

    summary += f"\n---\n\n"

    return summary + '\n'.join(output_lines)


def main():
    parser = argparse.ArgumentParser(description="Extract changed sections from markdown for incremental review")
    parser.add_argument("file_path", help="Path to markdown file")
    parser.add_argument("--context-sections", type=int, default=0,
                       help="Number of sibling sections to include as context (default: 0)")

    args = parser.parse_args()

    result = extract_changed_sections(args.file_path, args.context_sections)

    if not result:
        # No changes - signal caller to do full review
        sys.exit(1)

    print(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
