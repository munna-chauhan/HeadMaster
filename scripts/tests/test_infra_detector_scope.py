#!/usr/bin/env python
"""Unit tests for test_infra_detector.py"""

import pytest
import sys
import shutil
import tempfile
from pathlib import Path

# Add qa-integration scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "skills" / "qa-integration" / "scripts"))

from test_infra_detector import detect_infra, detect_build_system


def test_h2_with_test_scope_is_detected():
    """H2 with test scope should be detected as embedded_db."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        pom = repo / "pom.xml"
        pom.write_text("""<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <dependencies>
    <dependency>
      <groupId>com.h2database</groupId>
      <artifactId>h2</artifactId>
      <version>2.1.214</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
""")

        build_system = detect_build_system(repo)
        assert build_system == "maven"

        detected = detect_infra(repo, build_system, pom.read_text())

        assert "embedded_db" in detected, f"Expected embedded_db to be detected, got: {detected.keys()}"
        assert detected["embedded_db"]["capability"] == "MOCK_INTEGRATION"
        print("OK test_h2_with_test_scope_is_detected")


def test_h2_with_runtime_scope_is_not_detected():
    """H2 with runtime scope should NOT be detected as test infra (not available in tests)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        pom = repo / "pom.xml"
        pom.write_text("""<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <dependencies>
    <dependency>
      <groupId>com.h2database</groupId>
      <artifactId>h2</artifactId>
      <version>2.1.214</version>
      <scope>runtime</scope>
    </dependency>
  </dependencies>
</project>
""")

        build_system = detect_build_system(repo)
        assert build_system == "maven"

        detected = detect_infra(repo, build_system, pom.read_text())

        assert "embedded_db" not in detected, f"Expected embedded_db NOT to be detected (runtime scope), got: {detected.keys()}"
        print("OK test_h2_with_runtime_scope_is_not_detected")


if __name__ == "__main__":
    print("Running test_infra_detector unit tests...\n")

    try:
        test_h2_with_test_scope_is_detected()
        test_h2_with_runtime_scope_is_not_detected()

        print("\nOK All infra detector tests passed")
    except Exception as e:
        print(f"\nX Test failed: {e}")
        raise
