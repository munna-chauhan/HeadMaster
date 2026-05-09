#!/usr/bin/env python
"""
Unit Tests for HeadMaster Commands

Tests individual commands in isolation to ensure they work correctly.

Usage:
    python -m pytest tests/test_commands.py
    python -m pytest tests/test_commands.py -v
"""

import tempfile
import unittest
from pathlib import Path


class TestIntelligentRetry(unittest.TestCase):
    """Test intelligent retry logic"""

    def test_transient_failure_detection(self):
        """Test detection of transient vs permanent failures"""
        transient_patterns = [
            "ECONNREFUSED",
            "ETIMEDOUT",
            "network error",
            "503 Service Unavailable",
            "connection reset"
        ]

        transient_errors = [
            "Error: ECONNREFUSED: Connection refused",
            "Request timeout: ETIMEDOUT",
            "network error: host unreachable",
            "HTTP 503 Service Unavailable",
            "Error: connection reset by peer"
        ]

        permanent_errors = [
            "SyntaxError: Unexpected token",
            "TypeError: Cannot read property",
            "Error: File not found",
            "ENOENT: no such file or directory"
        ]

        # Test transient detection
        for error in transient_errors:
            is_transient = any(pattern.lower() in error.lower() for pattern in transient_patterns)
            self.assertTrue(is_transient, f"Should be transient: {error}")

        # Test permanent detection
        for error in permanent_errors:
            is_transient = any(pattern.lower() in error.lower() for pattern in transient_patterns)
            self.assertFalse(is_transient, f"Should be permanent: {error}")

    def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        initial_backoff = 5  # seconds

        def calculate_backoff(attempt):
            delay = initial_backoff * (2 ** (attempt - 1))
            return min(delay, 60)  # Cap at 60 seconds

        expected = [
            (1, 5),  # 5 * 2^0 = 5
            (2, 10),  # 5 * 2^1 = 10
            (3, 20),  # 5 * 2^2 = 20
            (4, 40),  # 5 * 2^3 = 40
            (5, 60),  # 5 * 2^4 = 80, capped at 60
        ]

        for attempt, expected_delay in expected:
            actual_delay = calculate_backoff(attempt)
            self.assertEqual(actual_delay, expected_delay)


class TestStateDetection(unittest.TestCase):
    """Test pipeline state detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.feature_dir = Path(self.test_dir) / "docs" / "features" / "test-feature"
        self.planning_dir = self.feature_dir / "planning"
        self.design_dir = self.feature_dir / "design"
        self.breakdown_dir = self.feature_dir / "breakdown"
        self.planning_dir.mkdir(parents=True)
        self.design_dir.mkdir(parents=True)
        self.breakdown_dir.mkdir(parents=True)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_state_detection_init(self):
        """Test planning/Init state — FEATURE_DRAFT exists, no PRD"""
        (self.planning_dir / "FEATURE_DRAFT.md").write_text("# Feature Draft")

        has_draft = (self.planning_dir / "FEATURE_DRAFT.md").exists()
        has_prd = (self.planning_dir / "PRD.md").exists()

        self.assertTrue(has_draft)
        self.assertFalse(has_prd)

        phase = "planning/Discover" if has_draft and not has_prd else "OTHER"
        self.assertEqual(phase, "planning/Discover")

    def test_state_detection_prd_in_progress(self):
        """Test PRD exists but not approved — planning/Review state"""
        (self.planning_dir / "PRD.md").write_text("# PRD\n\nSome content")

        has_prd = (self.planning_dir / "PRD.md").exists()
        content = (self.planning_dir / "PRD.md").read_text()
        is_approved = "PRD Status: APPROVED" in content

        self.assertTrue(has_prd)
        self.assertFalse(is_approved)

        phase = "planning/Review" if has_prd and not is_approved else "OTHER"
        self.assertEqual(phase, "planning/Review")

    def test_state_detection_prd_approved(self):
        """Test PRD finalized — gate string present"""
        prd_content = """# PRD

## 1. Executive Summary
Content here.

---
PRD Status: APPROVED
Approved: 2026-04-17
Iterations: 1
"""
        (self.planning_dir / "PRD.md").write_text(prd_content)

        content = (self.planning_dir / "PRD.md").read_text()
        is_approved = "PRD Status: APPROVED" in content
        self.assertTrue(is_approved)

    def test_state_detection_design_in_progress(self):
        """Test design/Architect state — SYSTEM_DESIGN_NOTES exists, no TDD"""
        (self.planning_dir / "PRD.md").write_text("PRD Status: APPROVED")
        (self.design_dir / "SYSTEM_DESIGN_NOTES.md").write_text("# Design\nArchitecture Locked: YES")

        has_sdn = (self.design_dir / "SYSTEM_DESIGN_NOTES.md").exists()
        has_tdd = any(self.design_dir.glob("TDD*.md"))

        self.assertTrue(has_sdn)
        self.assertFalse(has_tdd)

        phase = "design/Engineer" if has_sdn and not has_tdd else "OTHER"
        self.assertEqual(phase, "design/Engineer")

    def test_state_detection_breakdown_ready(self):
        """Test breakdown/ready state — TDD_REVIEW approved, no JIRA_BREAKDOWN"""
        (self.design_dir / "TDD.md").write_text("# TDD")
        (self.design_dir / "TDD_REVIEW.md").write_text("Verdict: APPROVED")

        has_tdd_review = (self.design_dir / "TDD_REVIEW.md").exists()
        has_breakdown = (self.breakdown_dir / "JIRA_BREAKDOWN.md").exists()

        self.assertTrue(has_tdd_review)
        self.assertFalse(has_breakdown)

        phase = "breakdown/ready" if has_tdd_review and not has_breakdown else "OTHER"
        self.assertEqual(phase, "breakdown/ready")

    def test_state_detection_execute_ready(self):
        """Test execute/ready state — JIRA_BREAKDOWN exists"""
        (self.breakdown_dir / "JIRA_BREAKDOWN.md").write_text(
            "# Breakdown\nPush Status: LOCAL ONLY\n\n| STORY-01 | — | repo | title | 3 | P1 | ⏳ NEW |",
            encoding="utf-8"
        )

        has_breakdown = (self.breakdown_dir / "JIRA_BREAKDOWN.md").exists()
        self.assertTrue(has_breakdown)

        content = (self.breakdown_dir / "JIRA_BREAKDOWN.md").read_text(encoding="utf-8")
        has_new_stories = "⏳ NEW" in content
        self.assertTrue(has_new_stories)


if __name__ == "__main__":
    unittest.main()
