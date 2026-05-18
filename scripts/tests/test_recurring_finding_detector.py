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
"""Tests for recurring_finding_detector.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from recurring_finding_detector import (
    _extract_findings,
    _group_findings,
    _to_memory_entry,
    _word_overlap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_review(tmp_path: Path, story_key: str, lines: list[str]) -> Path:
    f = tmp_path / f"code-review-{story_key}.md"
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# _extract_findings
# ---------------------------------------------------------------------------

def test_extract_high_finding():
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("HIGH: SQL query built with string concatenation — SQL injection risk\n")
        f.write("No issues found in other checks.\n")
        name = f.name
    findings = _extract_findings(Path(name))
    os.unlink(name)
    assert len(findings) == 1
    assert findings[0][0] == "HIGH"
    assert "SQL" in findings[0][1]


def test_extract_skips_trivially_short_lines():
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("HIGH: ok\n")  # < 4 words
        name = f.name
    findings = _extract_findings(Path(name))
    os.unlink(name)
    assert findings == []


def test_extract_multiple_severities(tmp_path: Path):
    p = tmp_path / "review.md"
    p.write_text(
        "HIGH: Missing input validation on user-controlled parameter\n"
        "MEDIUM: Error message exposes internal stack trace to caller\n"
        "LOW: Unused import left in production code\n"
    )
    findings = _extract_findings(p)
    severities = [f[0] for f in findings]
    assert "HIGH" in severities
    assert "MEDIUM" in severities
    assert "LOW" in severities


# ---------------------------------------------------------------------------
# _group_findings
# ---------------------------------------------------------------------------

def test_same_finding_two_stories_groups():
    per_story = {
        "STORY-1": [("HIGH", "HIGH: Missing input validation on user-controlled parameter causes injection")],
        "STORY-2": [("HIGH", "HIGH: Missing input validation on user-controlled parameter injection risk")],
    }
    groups = _group_findings(per_story)
    assert len(groups) == 1
    assert len(groups[0]["stories"]) == 2


def test_different_findings_no_group():
    per_story = {
        "STORY-1": [("HIGH", "HIGH: SQL injection via string concatenation in query builder")],
        "STORY-2": [("HIGH", "HIGH: Missing authentication check on admin endpoint handler")],
    }
    groups = _group_findings(per_story)
    assert groups == []


def test_severity_mismatch_no_group():
    per_story = {
        "STORY-1": [("HIGH",   "HIGH: hardcoded credentials found in configuration file class")],
        "STORY-2": [("MEDIUM", "MEDIUM: hardcoded credentials found in configuration file class")],
    }
    groups = _group_findings(per_story)
    assert groups == []


def test_single_story_never_groups():
    per_story = {
        "STORY-1": [
            ("HIGH", "HIGH: Missing input validation on user-controlled parameter"),
            ("HIGH", "HIGH: Missing input validation on user-controlled parameter again"),
        ]
    }
    groups = _group_findings(per_story)
    assert groups == []


def test_three_stories_same_finding():
    finding = ("MEDIUM", "MEDIUM: error message exposes internal stack trace to caller response")
    per_story = {"S-1": [finding], "S-2": [finding], "S-3": [finding]}
    groups = _group_findings(per_story)
    assert len(groups) == 1
    assert len(groups[0]["stories"]) == 3


# ---------------------------------------------------------------------------
# _to_memory_entry
# ---------------------------------------------------------------------------

def test_memory_entry_format():
    group = {
        "severity": "HIGH",
        "text": "HIGH: Missing input validation on user-controlled parameter",
        "stories": {"STORY-1", "STORY-2"},
    }
    entry = _to_memory_entry(group)
    assert "HIGH" in entry
    assert "2 stories" in entry
    assert len(entry) <= 200  # fits in one memory line


# ---------------------------------------------------------------------------
# _word_overlap
# ---------------------------------------------------------------------------

def test_overlap_identical():
    assert _word_overlap("missing input validation", "missing input validation") == 1.0


def test_overlap_paraphrase():
    score = _word_overlap(
        "missing input validation on user parameter",
        "input validation missing for user-controlled parameter",
    )
    assert score >= 0.50


def test_overlap_unrelated():
    score = _word_overlap(
        "sql injection via string concatenation",
        "missing authentication on admin endpoint",
    )
    assert score < 0.30
