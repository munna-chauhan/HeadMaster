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
"""Test diff_review_filter.py logic"""

import sys
import tempfile
from pathlib import Path

# Add scripts to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from diff_review_filter import (
    parse_diff_hunks,
    extract_section_headers,
    find_containing_sections,
    get_section_range
)

def test_parse_diff_hunks():
    """Test diff hunk parsing"""
    diff = """
@@ -10,5 +10,7 @@ context
+added line 1
+added line 2
-removed line
@@ -30,3 +32,4 @@ more context
+another change
"""
    hunks = parse_diff_hunks(diff)
    assert len(hunks) == 2, f"Expected 2 hunks, got {len(hunks)}"
    assert hunks[0] == (10, 16), f"Expected (10, 16), got {hunks[0]}"
    assert hunks[1] == (32, 35), f"Expected (32, 35), got {hunks[1]}"
    print("PASS test_parse_diff_hunks")


def test_extract_section_headers():
    """Test section header extraction"""
    content = """# Level 1
Some text
## Level 2
More text
### Level 3
Content
## Another Level 2
Final text"""

    sections = extract_section_headers(content)
    assert len(sections) == 4, f"Expected 4 sections, got {len(sections)}"
    assert sections[0] == ("Level 1", 1, 1)
    assert sections[1] == ("Level 2", 3, 2)
    assert sections[2] == ("Level 3", 5, 3)
    assert sections[3] == ("Another Level 2", 7, 2)
    print("PASS test_extract_section_headers")


def test_find_containing_sections():
    """Test finding containing section headers"""
    sections = [
        ("Top", 1, 1),
        ("Section A", 5, 2),
        ("Subsection A1", 10, 3),
        ("Section B", 15, 2),
    ]

    # Line 12 is in Subsection A1, which is in Section A, which is in Top
    containing = find_containing_sections(12, sections)
    assert "Top" in containing, f"Expected 'Top', got {containing}"
    assert "Section A" in containing, f"Expected 'Section A', got {containing}"
    assert "Subsection A1" in containing, f"Expected 'Subsection A1', got {containing}"
    print("PASS test_find_containing_sections")


def test_get_section_range():
    """Test section range calculation"""
    sections = [
        ("Section A", 1, 1),
        ("Section B", 10, 1),
        ("Section C", 20, 1),
    ]

    # Section A goes from line 1 to 9 (before Section B starts)
    start, end = get_section_range(sections, 0, 30)
    assert start == 1 and end == 9, f"Expected (1, 9), got ({start}, {end})"

    # Section B goes from line 10 to 19
    start, end = get_section_range(sections, 1, 30)
    assert start == 10 and end == 19, f"Expected (10, 19), got ({start}, {end})"

    # Section C goes from line 20 to end (30)
    start, end = get_section_range(sections, 2, 30)
    assert start == 20 and end == 30, f"Expected (20, 30), got ({start}, {end})"

    print("PASS test_get_section_range")


if __name__ == "__main__":
    print("Running diff_review_filter tests...")
    print()

    test_parse_diff_hunks()
    test_extract_section_headers()
    test_find_containing_sections()
    test_get_section_range()

    print()
    print("All tests passed")
