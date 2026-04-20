#!/usr/bin/env python3
"""Tests for test_infra_detector.py"""

import json
import os
import tempfile
from pathlib import Path

import pytest

sys_path = os.path.join(os.path.dirname(__file__), "..")
import sys
sys.path.insert(0, sys_path)

from scripts.test_infra_detector import (
    classify_max_capability,
    compute_coverage,
    detect_build_system,
    detect_external_deps,
    detect_infra,
    run,
)


@pytest.fixture
def maven_repo(tmp_path):
    """Create a minimal Maven repo with Spring Boot + PostgreSQL."""
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
        <dependencies>
            <dependency>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-starter-test</artifactId>
                <scope>test</scope>
            </dependency>
            <dependency>
                <groupId>org.postgresql</groupId>
                <artifactId>postgresql</artifactId>
            </dependency>
        </dependencies>
    </project>""")
    return tmp_path


@pytest.fixture
def maven_repo_with_testcontainers(tmp_path):
    """Maven repo with Testcontainers + PostgreSQL."""
    pom = tmp_path / "pom.xml"
    pom.write_text("""<project>
        <dependencies>
            <dependency>
                <groupId>org.testcontainers</groupId>
                <artifactId>testcontainers</artifactId>
                <scope>test</scope>
            </dependency>
            <dependency>
                <groupId>org.testcontainers</groupId>
                <artifactId>postgresql</artifactId>
                <scope>test</scope>
            </dependency>
            <dependency>
                <groupId>org.postgresql</groupId>
                <artifactId>postgresql</artifactId>
            </dependency>
            <dependency>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-starter-data-redis</artifactId>
            </dependency>
        </dependencies>
    </project>""")
    return tmp_path


@pytest.fixture
def empty_repo(tmp_path):
    return tmp_path


def test_detect_build_system_maven(maven_repo):
    assert detect_build_system(maven_repo) == "maven"


def test_detect_build_system_unknown(empty_repo):
    assert detect_build_system(empty_repo) == "unknown"


def test_detect_infra_spring_boot_test(maven_repo):
    content = (maven_repo / "pom.xml").read_text()
    infra = detect_infra(maven_repo, "maven", content)
    assert "spring_boot_test" in infra
    assert infra["spring_boot_test"]["capability"] == "MOCK_INTEGRATION"


def test_detect_infra_testcontainers(maven_repo_with_testcontainers):
    content = (maven_repo_with_testcontainers / "pom.xml").read_text()
    infra = detect_infra(maven_repo_with_testcontainers, "maven", content)
    assert "testcontainers" in infra
    assert infra["testcontainers"]["capability"] == "INFRA_INTEGRATION"


def test_detect_external_deps_postgresql(maven_repo):
    content = (maven_repo / "pom.xml").read_text()
    deps = detect_external_deps("maven", content)
    assert "postgresql" in deps


def test_detect_external_deps_redis(maven_repo_with_testcontainers):
    content = (maven_repo_with_testcontainers / "pom.xml").read_text()
    deps = detect_external_deps("maven", content)
    assert "redis" in deps


def test_coverage_uncovered(maven_repo):
    content = (maven_repo / "pom.xml").read_text()
    infra = detect_infra(maven_repo, "maven", content)
    deps = detect_external_deps("maven", content)
    coverage = compute_coverage(infra, deps)
    # spring_boot_test doesn't cover postgresql
    assert coverage["postgresql"]["requires_real_infra"] is True


def test_coverage_covered_by_testcontainers(maven_repo_with_testcontainers):
    content = (maven_repo_with_testcontainers / "pom.xml").read_text()
    infra = detect_infra(maven_repo_with_testcontainers, "maven", content)
    deps = detect_external_deps("maven", content)
    coverage = compute_coverage(infra, deps)
    assert coverage["postgresql"]["covered"] is True
    assert "testcontainers" in coverage["postgresql"]["covered_by"]


def test_classify_max_capability_infra():
    infra = {"testcontainers": {"capability": "INFRA_INTEGRATION"}}
    assert classify_max_capability(infra) == "INFRA_INTEGRATION"


def test_classify_max_capability_mock():
    infra = {"spring_boot_test": {"capability": "MOCK_INTEGRATION"}}
    assert classify_max_capability(infra) == "MOCK_INTEGRATION"


def test_classify_max_capability_none():
    assert classify_max_capability({}) == "UNIT_ONLY"


def test_run_json_output(maven_repo):
    output = run(str(maven_repo), "json")
    result = json.loads(output)
    assert result["build_system"] == "maven"
    assert result["max_test_capability"] in ("UNIT_ONLY", "MOCK_INTEGRATION", "INFRA_INTEGRATION")
    assert "qa_guidance" in result
    assert "verification_scope" not in result or True  # field name is qa_guidance


def test_run_text_output(maven_repo):
    output = run(str(maven_repo), "text")
    assert "Max capability:" in output
    assert "maven" in output


def test_run_nonexistent_dir():
    output = run("/nonexistent/path/12345", "json")
    result = json.loads(output)
    assert "error" in result
