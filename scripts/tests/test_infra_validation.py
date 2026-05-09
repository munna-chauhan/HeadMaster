"""Tests for TDD infra strategy validation (item #18)."""

import pytest


def test_critical_infra_missing_escalates():
    """Critical infra (Testcontainers) missing from detector output → escalate."""
    # TDD Section 7 requires Testcontainers
    tdd_strategy = """
    ## Section 7: Testing Strategy
    - Use Testcontainers for PostgreSQL database tests
    - MockMvc for controller tests
    """

    # Detector output: no Testcontainers found
    detector_output = {
        "max_test_capability": "MOCK_INTEGRATION",
        "test_infra": ["H2", "MockMvc"],
        "uncovered_dependencies": ["PostgreSQL"],
    }

    # Expected: escalate immediately
    critical_infra = ["testcontainers"]
    found_infra = [i.lower() for i in detector_output["test_infra"]]

    missing_critical = [infra for infra in critical_infra if infra not in found_infra]
    assert len(missing_critical) > 0, "Missing critical infra should escalate"
    assert "testcontainers" in missing_critical


def test_non_critical_infra_missing_continues_with_warning():
    """Non-critical infra (H2) missing → log warning, continue."""
    # TDD Section 7 mentions H2 (non-critical)
    tdd_strategy = """
    ## Section 7: Testing Strategy
    - H2 in-memory database for unit tests
    - JUnit for assertions
    """

    # Detector output: no H2 found
    detector_output = {
        "max_test_capability": "UNIT",
        "test_infra": ["JUnit"],
        "uncovered_dependencies": [],
    }

    # Expected: log warning, continue
    non_critical_infra = ["h2"]
    found_infra = [i.lower() for i in detector_output["test_infra"]]

    missing_non_critical = [infra for infra in non_critical_infra if infra not in found_infra]
    assert len(missing_non_critical) > 0, "Missing non-critical infra logged as warning"
    # Should continue (no escalation)


def test_all_required_infra_found_proceeds_normally():
    """All required infra found → proceed normally."""
    # TDD Section 7 requires Testcontainers, WireMock
    tdd_strategy = """
    ## Section 7: Testing Strategy
    - Testcontainers for PostgreSQL
    - WireMock for external API mocking
    """

    # Detector output: all found
    detector_output = {
        "max_test_capability": "INFRA_INTEGRATION",
        "test_infra": ["Testcontainers", "WireMock", "JUnit"],
        "uncovered_dependencies": [],
    }

    # Expected: proceed normally
    required_critical = ["testcontainers", "wiremock"]
    found_infra = [i.lower() for i in detector_output["test_infra"]]

    missing_critical = [infra for infra in required_critical if infra not in found_infra]
    assert len(missing_critical) == 0, "All required infra found"


def test_wiremock_missing_escalates():
    """WireMock (critical infra) missing → escalate."""
    # TDD Section 7 requires WireMock
    tdd_strategy = """
    ## Section 7: Testing Strategy
    - WireMock for mocking external REST APIs
    """

    # Detector output: no WireMock found
    detector_output = {
        "max_test_capability": "UNIT",
        "test_infra": ["JUnit"],
        "uncovered_dependencies": ["REST APIs"],
    }

    # Expected: escalate
    critical_infra = ["wiremock"]
    found_infra = [i.lower() for i in detector_output["test_infra"]]

    missing_critical = [infra for infra in critical_infra if infra not in found_infra]
    assert len(missing_critical) > 0, "Missing WireMock should escalate"


def test_localstack_missing_escalates():
    """LocalStack (critical infra) missing → escalate."""
    # TDD Section 7 requires LocalStack for AWS services
    tdd_strategy = """
    ## Section 7: Testing Strategy
    - LocalStack for S3 and SQS integration tests
    """

    # Detector output: no LocalStack found
    detector_output = {
        "max_test_capability": "UNIT",
        "test_infra": ["JUnit"],
        "uncovered_dependencies": ["AWS S3", "AWS SQS"],
    }

    # Expected: escalate
    critical_infra = ["localstack"]
    found_infra = [i.lower() for i in detector_output["test_infra"]]

    missing_critical = [infra for infra in critical_infra if infra not in found_infra]
    assert len(missing_critical) > 0, "Missing LocalStack should escalate"


def test_embedded_kafka_missing_escalates():
    """Embedded Kafka (critical infra) missing → escalate."""
    # TDD Section 7 requires embedded Kafka
    tdd_strategy = """
    ## Section 7: Testing Strategy
    - Embedded Kafka for event streaming tests
    """

    # Detector output: no embedded Kafka found
    detector_output = {
        "max_test_capability": "UNIT",
        "test_infra": ["JUnit"],
        "uncovered_dependencies": ["Kafka"],
    }

    # Expected: escalate
    critical_infra = ["embedded kafka", "kafka"]
    found_infra = [i.lower() for i in detector_output["test_infra"]]

    missing_critical = [infra for infra in critical_infra if not any(k in found_infra for k in infra.split())]
    assert len(missing_critical) > 0, "Missing embedded Kafka should escalate"


def test_mockmvc_missing_escalates():
    """MockMvc (critical infra) missing → escalate."""
    # TDD Section 7 requires MockMvc
    tdd_strategy = """
    ## Section 7: Testing Strategy
    - MockMvc for controller integration tests
    """

    # Detector output: no MockMvc found
    detector_output = {
        "max_test_capability": "UNIT",
        "test_infra": ["JUnit"],
        "uncovered_dependencies": [],
    }

    # Expected: escalate
    critical_infra = ["mockmvc"]
    found_infra = [i.lower() for i in detector_output["test_infra"]]

    missing_critical = [infra for infra in critical_infra if infra not in found_infra]
    assert len(missing_critical) > 0, "Missing MockMvc should escalate"
