"""Tests for curate_agent_memory.py"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from curate_agent_memory import _curate, _entry_date, _entry_text, _word_overlap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(tmp_path: Path, lines: list[str]) -> Path:
    p = tmp_path / "MEMORY.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _dated(text: str, days_ago: int = 10) -> str:
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    return f"- [{d}] {text}"


# ---------------------------------------------------------------------------
# _entry_date / _entry_text
# ---------------------------------------------------------------------------

def test_entry_date_parses():
    line = "- [2025-01-15] some memory entry"
    assert _entry_date(line) == date(2025, 1, 15)


def test_entry_date_missing_returns_none():
    assert _entry_date("- plain entry without date") is None


def test_entry_text_strips_prefix():
    line = "- [2025-01-15] actual content here"
    assert _entry_text(line) == "actual content here"


def test_entry_text_no_date_strips_bullet():
    assert _entry_text("- plain entry") == "plain entry"


# ---------------------------------------------------------------------------
# _word_overlap
# ---------------------------------------------------------------------------

def test_overlap_identical():
    assert _word_overlap("missing input validation", "missing input validation") == 1.0


def test_overlap_partial():
    score = _word_overlap("always flag async AC sections", "flag async AC section in PRD")
    assert score >= 0.40


def test_overlap_unrelated():
    assert _word_overlap("sql injection risk", "missing authentication check") < 0.20


# ---------------------------------------------------------------------------
# _curate — age-out
# ---------------------------------------------------------------------------

def test_aged_out_old_entries(tmp_path):
    old = _dated("old entry to remove", days_ago=100)
    fresh = _dated("fresh entry to keep", days_ago=10)
    path = _make_memory(tmp_path, [old, fresh])
    r = _curate(path, age_days=90, dry_run=False)
    assert r["aged_out"] == 1
    assert r["changed"] is True
    remaining = path.read_text().splitlines()
    assert any("fresh entry" in l for l in remaining)
    assert not any("old entry" in l for l in remaining)


def test_no_aged_entries_unchanged(tmp_path):
    fresh = _dated("fresh entry", days_ago=5)
    path = _make_memory(tmp_path, [fresh])
    r = _curate(path, age_days=90, dry_run=False)
    assert r["aged_out"] == 0
    assert r["changed"] is False


# ---------------------------------------------------------------------------
# _curate — dedup / merge
# ---------------------------------------------------------------------------

def test_duplicate_entries_merged(tmp_path):
    a = _dated("always add async AC section for event-driven features", days_ago=20)
    b = _dated("add async AC section when feature involves event-driven flow", days_ago=5)
    path = _make_memory(tmp_path, [a, b])
    r = _curate(path, age_days=90, dry_run=False)
    assert r["merged"] == 1
    remaining = [l for l in path.read_text().splitlines() if l.strip().startswith("-")]
    assert len(remaining) == 1


def test_recent_entry_wins_on_merge(tmp_path):
    old = _dated("flag multi-repo scope early in design phase", days_ago=30)
    new = _dated("flag multi-repo scope early triggers epic reclassification", days_ago=3)
    path = _make_memory(tmp_path, [old, new])
    _curate(path, age_days=90, dry_run=False)
    content = path.read_text()
    assert "triggers epic reclassification" in content


def test_unrelated_entries_both_kept(tmp_path):
    a = _dated("always validate async AC sections in PRD review")
    b = _dated("SQL injection risk from string concatenation in query builder")
    path = _make_memory(tmp_path, [a, b])
    r = _curate(path, age_days=90, dry_run=False)
    assert r["merged"] == 0
    assert r["changed"] is False


# ---------------------------------------------------------------------------
# _curate — dry-run
# ---------------------------------------------------------------------------

def test_dry_run_does_not_write(tmp_path):
    old = _dated("entry to remove", days_ago=200)
    path = _make_memory(tmp_path, [old])
    original = path.read_text()
    r = _curate(path, age_days=90, dry_run=True)
    assert r["changed"] is True
    assert path.read_text() == original  # unchanged


# ---------------------------------------------------------------------------
# _curate — backup
# ---------------------------------------------------------------------------

def test_backup_created_on_change(tmp_path):
    old = _dated("old entry", days_ago=200)
    path = _make_memory(tmp_path, [old])
    _curate(path, age_days=90, dry_run=False)
    bak = path.with_suffix(".md.bak")
    assert bak.exists()
    assert "old entry" in bak.read_text()
