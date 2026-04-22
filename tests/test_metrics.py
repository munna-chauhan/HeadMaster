"""Tests for scripts/metrics.py — per-feature metrics collection and aggregation."""

import json
import os
import sys
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
METRICS_SCRIPT = REPO_ROOT / "scripts" / "metrics.py"

sys.path.insert(0, str(REPO_ROOT))
from scripts.metrics import (
    _metrics_path, _append_event, _load_events, _compute_feature_stats,
    cmd_emit, cmd_report, cmd_aggregate, VALID_EVENTS,
)


@pytest.fixture
def tmp_memory(tmp_path, monkeypatch):
    """Redirect MEMORY_DIR and SESSION_FILE to a temp directory."""
    import scripts.metrics as m
    monkeypatch.setattr(m, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(m, "SESSION_FILE", tmp_path / "session-budget.json")
    return tmp_path


@pytest.fixture
def slug():
    return "test-feature"


class TestEmit:
    def test_emit_creates_file(self, tmp_memory, slug):
        cmd_emit(slug, "gate_pass", phase="planning", stage="Draft")
        path = tmp_memory / slug / "metrics.jsonl"
        assert path.exists()
        events = _load_events_from(path)
        assert len(events) == 1
        assert events[0]["event"] == "gate_pass"
        assert events[0]["phase"] == "planning"
        assert events[0]["stage"] == "Draft"
        assert "ts" in events[0]

    def test_emit_appends(self, tmp_memory, slug):
        cmd_emit(slug, "gate_pass", phase="planning", stage="Draft")
        cmd_emit(slug, "gate_pass", phase="planning", stage="APPROVED")
        path = tmp_memory / slug / "metrics.jsonl"
        events = _load_events_from(path)
        assert len(events) == 2

    def test_emit_with_story(self, tmp_memory, slug):
        cmd_emit(slug, "story_start", phase="execute", stage="implement", story="PWRE-101")
        events = _load_events_from(tmp_memory / slug / "metrics.jsonl")
        assert events[0]["story"] == "PWRE-101"

    def test_emit_with_verdict(self, tmp_memory, slug):
        cmd_emit(slug, "gate_fail", phase="design", stage="Review", verdict="REJECTED")
        events = _load_events_from(tmp_memory / slug / "metrics.jsonl")
        assert events[0]["verdict"] == "REJECTED"

    def test_emit_with_extra(self, tmp_memory, slug):
        cmd_emit(slug, "story_complete", phase="execute", extra={"files": 3})
        events = _load_events_from(tmp_memory / slug / "metrics.jsonl")
        assert events[0]["extra"] == {"files": 3}

    def test_emit_invalid_event_type(self, tmp_memory, slug):
        with pytest.raises(SystemExit):
            cmd_emit(slug, "invalid_event")

    def test_emit_captures_session_tokens(self, tmp_memory, slug):
        # Write a fake session budget
        budget = {"total_tokens": 42000, "turn_count": 10}
        session_file = tmp_memory / "session-budget.json"
        session_file.write_text(json.dumps(budget), encoding="utf-8")
        cmd_emit(slug, "gate_pass", phase="planning", stage="Draft")
        events = _load_events_from(tmp_memory / slug / "metrics.jsonl")
        assert events[0]["session_tokens_est"] == 42000
        assert events[0]["session_turns"] == 10

    def test_emit_no_session_file(self, tmp_memory, slug):
        """Emit works even without session budget file."""
        cmd_emit(slug, "gate_pass", phase="planning", stage="Draft")
        events = _load_events_from(tmp_memory / slug / "metrics.jsonl")
        assert "session_tokens_est" not in events[0]


class TestLoadEvents:
    def test_load_empty(self, tmp_memory, slug):
        assert _load_events(slug) == []

    def test_load_with_corrupt_line(self, tmp_memory, slug):
        path = tmp_memory / slug / "metrics.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"event":"gate_pass"}\nBAD LINE\n{"event":"gate_fail"}\n', encoding="utf-8")
        events = _load_events(slug)
        assert len(events) == 2


class TestComputeStats:
    def _make_events(self):
        return [
            {"ts": "2025-01-01T00:00:00Z", "event": "gate_pass", "phase": "planning", "stage": "Draft", "session_tokens_est": 1000},
            {"ts": "2025-01-01T01:00:00Z", "event": "gate_pass", "phase": "planning", "stage": "APPROVED", "session_tokens_est": 5000},
            {"ts": "2025-01-01T02:00:00Z", "event": "gate_pass", "phase": "design", "stage": "APPROVED", "session_tokens_est": 15000},
            {"ts": "2025-01-01T03:00:00Z", "event": "story_start", "phase": "execute", "story": "S-1"},
            {"ts": "2025-01-01T03:30:00Z", "event": "story_complete", "phase": "execute", "story": "S-1"},
            {"ts": "2025-01-01T04:00:00Z", "event": "story_start", "phase": "execute", "story": "S-2"},
            {"ts": "2025-01-01T04:10:00Z", "event": "story_retry", "phase": "execute", "story": "S-2"},
            {"ts": "2025-01-01T04:30:00Z", "event": "story_complete", "phase": "execute", "story": "S-2", "session_tokens_est": 40000},
        ]

    def test_basic_stats(self):
        events = self._make_events()
        stats = _compute_feature_stats("test", events)
        assert stats["stories_total"] == 2
        assert stats["stories_complete"] == 2
        assert stats["first_pass_stories"] == 1  # S-1 passed first try, S-2 had retry
        assert stats["retries"] == 1
        assert stats["escalations"] == 0
        assert stats["gate_failures"] == 0

    def test_first_pass_rate(self):
        events = self._make_events()
        stats = _compute_feature_stats("test", events)
        assert stats["first_pass_rate"] == 50.0  # 1 of 2 stories first-pass

    def test_token_estimate(self):
        events = self._make_events()
        stats = _compute_feature_stats("test", events)
        assert stats["token_est_total"] == 39000  # 40000 - 1000

    def test_phase_sequence(self):
        events = self._make_events()
        stats = _compute_feature_stats("test", events)
        assert stats["phase_sequence"] == ["planning", "design", "execute"]

    def test_gate_failures(self):
        events = [
            {"ts": "2025-01-01T00:00:00Z", "event": "gate_fail", "phase": "planning", "stage": "Review", "verdict": "REJECTED"},
            {"ts": "2025-01-01T01:00:00Z", "event": "gate_pass", "phase": "planning", "stage": "APPROVED"},
        ]
        stats = _compute_feature_stats("test", events)
        assert stats["gate_failures"] == 1
        assert stats["phases"]["planning"]["failures"] == 1
        assert stats["phases"]["planning"]["passes"] == 1

    def test_escalation(self):
        events = [
            {"ts": "2025-01-01T00:00:00Z", "event": "story_start", "phase": "execute", "story": "S-1"},
            {"ts": "2025-01-01T01:00:00Z", "event": "escalation", "phase": "execute", "story": "S-1"},
        ]
        stats = _compute_feature_stats("test", events)
        assert stats["escalations"] == 1
        assert stats["stories_total"] == 1
        assert stats["stories_complete"] == 0

    def test_empty_events(self):
        stats = _compute_feature_stats("test", [])
        assert stats["events"] == 0
        assert stats["stories_total"] == 0
        assert stats["first_pass_rate"] is None


class TestAggregate:
    def test_aggregate_multiple_features(self, tmp_memory, capsys):
        # Feature 1: 2 stories, 1 retry
        _write_events(tmp_memory, "feat-a", [
            {"ts": "T1", "event": "story_start", "phase": "execute", "story": "A-1"},
            {"ts": "T2", "event": "story_complete", "phase": "execute", "story": "A-1"},
            {"ts": "T3", "event": "story_start", "phase": "execute", "story": "A-2"},
            {"ts": "T4", "event": "story_retry", "phase": "execute", "story": "A-2"},
            {"ts": "T5", "event": "story_complete", "phase": "execute", "story": "A-2"},
        ])
        # Feature 2: 1 story, 1 escalation
        _write_events(tmp_memory, "feat-b", [
            {"ts": "T1", "event": "story_start", "phase": "execute", "story": "B-1"},
            {"ts": "T2", "event": "escalation", "phase": "execute", "story": "B-1"},
        ])

        cmd_aggregate()
        output = json.loads(capsys.readouterr().out)
        assert output["totals"]["features"] == 2
        assert output["totals"]["stories"] == 3
        assert output["totals"]["retries"] == 1
        assert output["totals"]["escalations"] == 1

    def test_aggregate_empty(self, tmp_memory, capsys):
        cmd_aggregate()
        output = json.loads(capsys.readouterr().out)
        # MEMORY_DIR exists but has no feature subdirs with metrics
        assert output["totals"]["features"] == 0
        assert output["features"] == []

    def test_aggregate_skips_non_dirs(self, tmp_memory, capsys):
        (tmp_memory / "stray-file.txt").write_text("not a feature", encoding="utf-8")
        cmd_aggregate()
        output = json.loads(capsys.readouterr().out)
        assert output["totals"]["features"] == 0
        assert output["features"] == []


CLI_TEST_SLUG = "_cli_test_"
CLI_TEST_DIR = REPO_ROOT / "memory" / "features" / CLI_TEST_SLUG


class TestCLI:
    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        import shutil
        if CLI_TEST_DIR.exists():
            shutil.rmtree(CLI_TEST_DIR)

    def test_cli_emit(self):
        result = subprocess.run(
            [sys.executable, str(METRICS_SCRIPT), "emit", CLI_TEST_SLUG, "gate_pass",
             "--phase", "planning", "--stage", "Draft"],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0

    def test_cli_invalid_event(self):
        result = subprocess.run(
            [sys.executable, str(METRICS_SCRIPT), "emit", CLI_TEST_SLUG, "bogus"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_cli_report_no_data(self):
        result = subprocess.run(
            [sys.executable, str(METRICS_SCRIPT), "report", "nonexistent-slug"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["events"] == 0


class TestValidEvents:
    def test_all_event_types_documented(self):
        expected = {
            "gate_pass", "gate_fail", "phase_start",
            "story_start", "story_complete", "story_retry",
            "escalation", "feature_complete",
        }
        assert VALID_EVENTS == expected


# --- helpers ---

def _load_events_from(path: Path) -> list:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _write_events(memory_dir: Path, slug: str, events: list):
    path = memory_dir / slug / "metrics.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
