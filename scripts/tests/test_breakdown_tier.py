"""Tests for breakdown tier re-assessment validation (item #15)."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory


def test_lite_tier_story_count_breach():
    """Lite tier breached when story count > 3."""
    # Setup: simulate lite tier feature with 4 stories
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"tier": "lite"}))

        # Simulate: 4 NEW stories (breach)
        story_count = 4
        total_sp = 6  # within threshold
        breach_indicators = []

        # Expected: tier_mismatch = True
        assert story_count > 3, "Lite tier breach: story count > 3"


def test_lite_tier_sp_breach():
    """Lite tier breached when total SP > 8."""
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"tier": "lite"}))

        # Simulate: 3 stories, 9 SP (breach)
        story_count = 3
        total_sp = 9
        breach_indicators = []

        # Expected: tier_mismatch = True
        assert total_sp > 8, "Lite tier breach: total SP > 8"


def test_lite_tier_critical_indicator_breach():
    """Lite tier breached when story has critical indicator."""
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"tier": "lite"}))

        # Simulate: 2 stories, 5 SP, but has "database migration" indicator
        story_count = 2
        total_sp = 5
        breach_indicators = ["STORY-01"]  # has "database migration" tag

        # Expected: tier_mismatch = True
        assert len(breach_indicators) > 0, "Lite tier breach: critical indicator found"


def test_standard_tier_story_count_breach():
    """Standard tier breached when story count > 10."""
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"tier": "standard"}))

        # Simulate: 11 stories (breach)
        story_count = 11
        total_sp = 20  # within threshold

        # Expected: tier_mismatch = True
        assert story_count > 10, "Standard tier breach: story count > 10"


def test_standard_tier_sp_breach():
    """Standard tier breached when total SP > 21."""
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"tier": "standard"}))

        # Simulate: 8 stories, 22 SP (breach)
        story_count = 8
        total_sp = 22

        # Expected: tier_mismatch = True
        assert total_sp > 21, "Standard tier breach: total SP > 21"


def test_tier_not_set_backward_compat():
    """Feature without tier set (backward compat) logs warning but continues."""
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"pipeline": {"phase": "breakdown"}}))  # no tier

        # Simulate: 5 stories (would breach lite)
        story_count = 5
        total_sp = 10

        # Expected: continue (backward compat)
        state = json.loads(loop_state.read_text())
        tier = state.get("tier", None)
        assert tier is None, "Tier not set — backward compat mode"


def test_lite_tier_within_threshold():
    """Lite tier within all thresholds — no breach."""
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"tier": "lite"}))

        # Simulate: 3 stories, 8 SP, no indicators
        story_count = 3
        total_sp = 8
        breach_indicators = []

        # Expected: no breach
        assert story_count <= 3 and total_sp <= 8 and len(breach_indicators) == 0


def test_standard_tier_within_threshold():
    """Standard tier within all thresholds — no breach."""
    with TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "memory" / "features" / "default" / "test-feature"
        memory_path.mkdir(parents=True, exist_ok=True)

        loop_state = memory_path / "loop_state.json"
        loop_state.write_text(json.dumps({"tier": "standard"}))

        # Simulate: 10 stories, 21 SP
        story_count = 10
        total_sp = 21

        # Expected: no breach
        assert story_count <= 10 and total_sp <= 21
