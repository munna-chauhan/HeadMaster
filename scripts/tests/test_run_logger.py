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
"""Tests for run_logger.py"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from run_logger import log_decision


def test_log_decision_creates_file_if_missing(tmp_path):
    """Log decision creates run-log.md if it doesn't exist."""
    # Mock HeadMaster root
    hm_root = tmp_path
    project = "acme"
    slug = "test-feature"

    # Override path resolution by monkeypatching
    import run_logger
    original_file = run_logger.__file__
    run_logger.__file__ = str(hm_root / "scripts" / "run_logger.py")

    try:
        log_decision(project, slug, "Planning/Discover", "AUTO_RESOLVE", "Gap: logging strategy")

        log_path = hm_root / "memory" / "features" / project / slug / "run-log.md"
        assert log_path.exists(), "run-log.md should be created"

        content = log_path.read_text(encoding="utf-8")
        assert "[Planning/Discover]" in content
        assert "[AUTO_RESOLVE]" in content
        assert 'input="Gap: logging strategy"' in content
    finally:
        run_logger.__file__ = original_file


def test_log_decision_appends_not_overwrites(tmp_path):
    """Log decision appends entries, does not overwrite existing log."""
    import run_logger
    original_file = run_logger.__file__
    run_logger.__file__ = str(tmp_path / "scripts" / "run_logger.py")

    try:
        project = "acme"
        slug = "test-feature"

        # First entry
        log_decision(project, slug, "Planning/Discover", "AUTO_RESOLVE", "Gap 1")

        # Second entry
        log_decision(project, slug, "Design/Architect", "ESCALATE", "Trade-off: DB choice")

        log_path = tmp_path / "memory" / "features" / project / slug / "run-log.md"
        content = log_path.read_text(encoding="utf-8")

        lines = [line for line in content.strip().split("\n") if line]
        assert len(lines) == 2, "Should have 2 entries"
        assert "Gap 1" in lines[0]
        assert "Trade-off: DB choice" in lines[1]
    finally:
        run_logger.__file__ = original_file


def test_log_decision_includes_confidence_if_provided(tmp_path):
    """Log decision includes confidence level when provided."""
    import run_logger
    original_file = run_logger.__file__
    run_logger.__file__ = str(tmp_path / "scripts" / "run_logger.py")

    try:
        project = "acme"
        slug = "test-feature"

        log_decision(project, slug, "Breakdown/Decompose", "AUTO_CREATE_EPIC", "5 stories, 13 SP", confidence="HIGH")

        log_path = tmp_path / "memory" / "features" / project / slug / "run-log.md"
        content = log_path.read_text(encoding="utf-8")

        assert "confidence=HIGH" in content
    finally:
        run_logger.__file__ = original_file


def test_log_decision_omits_confidence_if_none(tmp_path):
    """Log decision omits confidence field when not provided."""
    import run_logger
    original_file = run_logger.__file__
    run_logger.__file__ = str(tmp_path / "scripts" / "run_logger.py")

    try:
        project = "acme"
        slug = "test-feature"

        log_decision(project, slug, "Execute/Phase A", "RETRY", "Build failed: missing import")

        log_path = tmp_path / "memory" / "features" / project / slug / "run-log.md"
        content = log_path.read_text(encoding="utf-8")

        assert "confidence=" not in content
    finally:
        run_logger.__file__ = original_file


def test_log_decision_iso_timestamp_format(tmp_path):
    """Log decision uses ISO 8601 timestamp format."""
    import run_logger
    original_file = run_logger.__file__
    run_logger.__file__ = str(tmp_path / "scripts" / "run_logger.py")

    try:
        project = "acme"
        slug = "test-feature"

        log_decision(project, slug, "Planning/Draft", "CONFLICT_FOUND", "Cache TTL contradicts Section 3")

        log_path = tmp_path / "memory" / "features" / project / slug / "run-log.md"
        content = log_path.read_text(encoding="utf-8")

        # Check for ISO 8601 format: [YYYY-MM-DDTHH:MM:SS+00:00]
        assert content.startswith("[20"), "Should start with ISO timestamp"
        assert "T" in content.split("]")[0], "Timestamp should include T separator"
    finally:
        run_logger.__file__ = original_file


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
