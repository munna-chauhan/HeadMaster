#!/usr/bin/env python
"""Unit tests for workflow_config.py"""

import json
import pytest
import subprocess
import sys
import yaml
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import workflow_config


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def use_real_workflows():
    """Tests use the actual workflow yml files — no mocking.
    This validates the real files are well-formed and queryable."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Tier file loading
# ─────────────────────────────────────────────────────────────────────────────

class TestTierFileLoading:

    def test_all_tier_files_exist(self):
        for tier in ("xs", "s", "m", "l"):
            path = workflow_config.WORKFLOWS_DIR / f"{tier}.yml"
            assert path.exists(), f"Missing tier file: {path}"

    def test_all_non_tier_files_exist(self):
        for name in ("classification", "reclassification", "stage-skip-rules"):
            path = workflow_config.WORKFLOWS_DIR / f"{name}.yml"
            assert path.exists(), f"Missing workflow file: {path}"

    def test_all_tier_files_parse_as_valid_yaml(self):
        for tier in ("xs", "s", "m", "l"):
            data = workflow_config.get(tier)
            assert isinstance(data, dict), f"{tier}.yml did not parse to dict"
            assert "stages" in data, f"{tier}.yml missing 'stages' key"

    def test_invalid_tier_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            workflow_config.get("xxl")


# ─────────────────────────────────────────────────────────────────────────────
# get() — dotpath resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestGet:

    def test_get_full_tier_returns_dict(self):
        data = workflow_config.get("xs")
        assert isinstance(data, dict)
        assert "description" in data

    def test_get_nested_value(self):
        status = workflow_config.get("xs", "stages.prd.status")
        assert status == "skip"

    def test_get_list_value(self):
        sections = workflow_config.get("s", "stages.prd.sections")
        assert isinstance(sections, list)
        assert len(sections) == 10
        assert "Executive Summary" in sections

    def test_get_nonexistent_path_returns_none(self):
        result = workflow_config.get("xs", "stages.nonexistent.foo")
        assert result is None

    def test_get_deeply_nested(self):
        result = workflow_config.get("classification", "ai_classification.confidence.high")
        assert result is not None
        assert "auto-assign" in str(result).lower() or "agree" in str(result).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience functions
# ─────────────────────────────────────────────────────────────────────────────

class TestConvenienceFunctions:

    def test_get_stages_returns_dict(self):
        stages = workflow_config.get_stages("m")
        assert isinstance(stages, dict)
        assert "prd" in stages
        assert "tdd" in stages
        assert "execute" in stages

    def test_get_sections_returns_list(self):
        sections = workflow_config.get_sections("l", "prd")
        assert isinstance(sections, list)
        assert len(sections) == 14
        assert "Appendix" in sections

    def test_get_sections_for_skip_stage_returns_empty(self):
        sections = workflow_config.get_sections("xs", "prd")
        assert sections == []

    def test_get_status_required(self):
        assert workflow_config.get_status("l", "prd") == "required"

    def test_get_status_skip(self):
        assert workflow_config.get_status("xs", "prd") == "skip"

    def test_get_status_optional(self):
        assert workflow_config.get_status("xs", "tdd") == "optional"

    def test_get_artifact_returns_name(self):
        assert workflow_config.get_artifact("xs", "tdd") == "IMPLEMENTATION_BRIEF.md"
        assert workflow_config.get_artifact("s", "tdd") == "TDD.md"

    def test_get_artifact_for_skip_returns_none(self):
        assert workflow_config.get_artifact("xs", "prd") is None

    def test_get_gate(self):
        gate = workflow_config.get_gate("s", "prd")
        assert gate is not None
        assert "10 sections" in gate

    def test_get_escalation_thresholds(self):
        thresholds = workflow_config.get_escalation_thresholds("xs")
        assert isinstance(thresholds, dict)
        assert thresholds["story_count"] == 2
        assert thresholds["story_points"] == 5

    def test_get_escalation_thresholds_l_returns_empty(self):
        thresholds = workflow_config.get_escalation_thresholds("l")
        assert thresholds == {}

    def test_get_skip_rules(self):
        rules = workflow_config.get_skip_rules("discovery")
        assert isinstance(rules, dict)
        assert "skip_if" in rules

    def test_get_skip_rules_merge_gate_never(self):
        rules = workflow_config.get_skip_rules("merge_gate")
        assert rules.get("skip_if") == "never"


# ─────────────────────────────────────────────────────────────────────────────
# Reclassification
# ─────────────────────────────────────────────────────────────────────────────

class TestReclassification:

    def test_get_reclassification_returns_dict(self):
        data = workflow_config.get_reclassification()
        assert isinstance(data, dict)
        assert "checkpoints" in data
        assert "rework" in data

    def test_get_rework_same_tier_returns_empty(self):
        assert workflow_config.get_rework("s", "s") == []

    def test_get_rework_xs_to_s(self):
        rework = workflow_config.get_rework("xs", "s")
        assert isinstance(rework, list)
        assert len(rework) > 0
        assert any("PRD" in item for item in rework)

    def test_get_rework_s_to_m(self):
        rework = workflow_config.get_rework("s", "m")
        assert isinstance(rework, list)
        assert any("System Design" in item for item in rework)

    def test_get_rework_m_to_l(self):
        rework = workflow_config.get_rework("m", "l")
        assert isinstance(rework, list)
        assert any("Deployment Architecture" in item or "Appendix" in item for item in rework)


# ─────────────────────────────────────────────────────────────────────────────
# Classification
# ─────────────────────────────────────────────────────────────────────────────

class TestClassification:

    def test_get_classification_returns_dict(self):
        data = workflow_config.get_classification()
        assert isinstance(data, dict)
        assert "user_declared" in data
        assert "ai_classification" in data

    def test_classification_has_deterministic_signals(self):
        signals = workflow_config.get("classification", "ai_classification.deterministic_signals")
        assert isinstance(signals, list)
        assert len(signals) >= 3

    def test_classification_has_algorithm(self):
        algo = workflow_config.get("classification", "ai_classification.algorithm")
        assert algo is not None
        assert "deterministic" in algo.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Tier consistency — cross-tier validation
# ─────────────────────────────────────────────────────────────────────────────

class TestTierConsistency:

    def test_prd_section_count_increases_with_tier(self):
        xs_count = len(workflow_config.get_sections("xs", "prd"))
        s_count = len(workflow_config.get_sections("s", "prd"))
        m_count = len(workflow_config.get_sections("m", "prd"))
        l_count = len(workflow_config.get_sections("l", "prd"))
        assert xs_count == 0  # xs skips PRD
        assert s_count < m_count <= l_count

    def test_tdd_section_count_increases_with_tier(self):
        xs_count = len(workflow_config.get_sections("xs", "tdd"))
        s_count = len(workflow_config.get_sections("s", "tdd"))
        m_count = len(workflow_config.get_sections("m", "tdd"))
        l_count = len(workflow_config.get_sections("l", "tdd"))
        assert xs_count < s_count < m_count <= l_count

    def test_execute_required_in_all_tiers(self):
        for tier in ("xs", "s", "m", "l"):
            assert workflow_config.get_status(tier, "execute") == "required"

    def test_xs_skips_most_stages(self):
        for stage in ("discovery", "prd", "prd_review", "system_design", "tdd_review", "system_review"):
            assert workflow_config.get_status("xs", stage) == "skip", f"xs should skip {stage}"

    def test_l_requires_all_review_stages(self):
        for stage in ("prd_review", "tdd_review", "system_review"):
            assert workflow_config.get_status("l", stage) == "required", f"l should require {stage}"

    def test_escalation_thresholds_increase_with_tier(self):
        xs_t = workflow_config.get_escalation_thresholds("xs")
        s_t = workflow_config.get_escalation_thresholds("s")
        m_t = workflow_config.get_escalation_thresholds("m")
        assert xs_t["story_count"] < s_t["story_count"] < m_t["story_count"]
        assert xs_t["story_points"] < s_t["story_points"] < m_t["story_points"]

    def test_all_tiers_have_branches(self):
        for tier in ("xs", "s", "m", "l"):
            branches = workflow_config.get(tier, "branches")
            assert branches is not None, f"{tier} missing branches"

    def test_tdd_artifact_name_per_tier(self):
        assert workflow_config.get_artifact("xs", "tdd") == "IMPLEMENTATION_BRIEF.md"
        for tier in ("s", "m", "l"):
            artifact = workflow_config.get_artifact(tier, "tdd")
            assert "TDD" in artifact, f"{tier} tdd artifact should contain TDD"


# ─────────────────────────────────────────────────────────────────────────────
# CLI interface
# ─────────────────────────────────────────────────────────────────────────────

class TestCLI:

    def _run(self, *args):
        cmd = [sys.executable, str(Path(__file__).parent.parent / "workflow_config.py")] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                cwd=str(workflow_config.REPO_ROOT))
        return result

    def test_cli_tier_sections(self):
        r = self._run("s", "stages.prd.sections")
        assert r.returncode == 0
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 10
        assert "Executive Summary" in lines

    def test_cli_scalar_value(self):
        r = self._run("xs", "stages.prd.status")
        assert r.returncode == 0
        assert r.stdout.strip() == "skip"

    def test_cli_json_output_for_dict(self):
        r = self._run("xs", "escalation_thresholds")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["story_count"] == 2

    def test_cli_invalid_tier_fails(self):
        r = self._run("xxl", "stages.prd.status")
        assert r.returncode != 0

    def test_cli_invalid_path_fails(self):
        r = self._run("xs", "nonexistent.path")
        assert r.returncode != 0

    def test_cli_no_args_shows_usage(self):
        r = self._run()
        assert r.returncode != 0
        assert "Usage" in r.stderr

    def test_cli_non_tier_file(self):
        r = self._run("stage-skip-rules", "rules.merge_gate.skip_if")
        assert r.returncode == 0
        assert "never" in r.stdout.strip()
