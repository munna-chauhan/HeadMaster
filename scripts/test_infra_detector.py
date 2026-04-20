#!/usr/bin/env python3
"""Detect available test infrastructure in a repository.

Scans build files, test directories, and Docker configs to determine
what level of test verification is possible without external services.

Usage:
    python3 scripts/test_infra_detector.py --repo /path/to/repo [--format json|text]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# Patterns that indicate test infrastructure capabilities
INFRA_SIGNATURES = {
    "testcontainers": {
        "maven": [r"testcontainers", r"org\.testcontainers"],
        "gradle": [r"testcontainers"],
        "npm": [r"testcontainers"],
        "files": [],
        "capability": "INFRA_INTEGRATION",
        "description": "Testcontainers — can spin up real DB/queue/cache in Docker for tests",
    },
    "localstack": {
        "maven": [r"localstack"],
        "gradle": [r"localstack"],
        "npm": [r"localstack", r"@aws-sdk.*mock"],
        "files": ["localstack", "docker-compose"],
        "capability": "INFRA_INTEGRATION",
        "description": "LocalStack — can mock AWS services (S3, SQS, DynamoDB) locally",
    },
    "embedded_db": {
        "maven": [r"h2database", r"hsqldb", r"embedded-database-spring-test", r"flapdoodle"],
        "gradle": [r"h2database", r"hsqldb", r"flapdoodle"],
        "npm": [r"sqlite3", r"better-sqlite3"],
        "files": [],
        "capability": "MOCK_INTEGRATION",
        "description": "Embedded/in-memory DB available for data layer tests",
    },
    "wiremock": {
        "maven": [r"wiremock"],
        "gradle": [r"wiremock"],
        "npm": [r"nock", r"msw"],
        "files": [],
        "capability": "MOCK_INTEGRATION",
        "description": "HTTP mock server — can simulate external API calls",
    },
    "embedded_redis": {
        "maven": [r"embedded-redis", r"ozimov.*embedded"],
        "gradle": [r"embedded-redis"],
        "npm": [r"ioredis-mock", r"redis-mock"],
        "files": [],
        "capability": "MOCK_INTEGRATION",
        "description": "Embedded Redis — can test cache layer without real Redis",
    },
    "spring_boot_test": {
        "maven": [r"spring-boot-starter-test"],
        "gradle": [r"spring-boot-starter-test"],
        "npm": [],
        "files": [],
        "capability": "MOCK_INTEGRATION",
        "description": "Spring Boot Test — @SpringBootTest, @DataJpaTest, @WebMvcTest available",
    },
    "docker_compose_test": {
        "maven": [],
        "gradle": [],
        "npm": [],
        "files": ["docker-compose.test", "docker-compose.ci"],
        "capability": "INFRA_INTEGRATION",
        "description": "Docker Compose test config — can stand up service dependencies",
    },
}

# External dependencies that require real infrastructure
EXTERNAL_DEPS = {
    "postgresql": {
        "maven": [r"postgresql", r"org\.postgresql"],
        "gradle": [r"postgresql"],
        "npm": [r"pg\b", r"knex", r"typeorm"],
        "service": "PostgreSQL database",
    },
    "redis": {
        "maven": [r"spring-boot-starter-data-redis", r"jedis", r"lettuce"],
        "gradle": [r"redis", r"jedis", r"lettuce"],
        "npm": [r"ioredis", r"redis\b"],
        "service": "Redis cache",
    },
    "elasticsearch": {
        "maven": [r"elasticsearch", r"opensearch"],
        "gradle": [r"elasticsearch", r"opensearch"],
        "npm": [r"@elastic/elasticsearch", r"@opensearch"],
        "service": "Elasticsearch/OpenSearch cluster",
    },
    "sqs": {
        "maven": [r"aws.*sqs", r"amazon.*sqs"],
        "gradle": [r"aws.*sqs"],
        "npm": [r"@aws-sdk/client-sqs", r"aws-sdk.*SQS"],
        "service": "AWS SQS queue",
    },
    "s3": {
        "maven": [r"aws.*s3", r"amazon.*s3"],
        "gradle": [r"aws.*s3"],
        "npm": [r"@aws-sdk/client-s3", r"aws-sdk.*S3"],
        "service": "AWS S3 bucket",
    },
    "kafka": {
        "maven": [r"kafka", r"spring-kafka"],
        "gradle": [r"kafka"],
        "npm": [r"kafkajs", r"node-rdkafka"],
        "service": "Kafka broker",
    },
}


def detect_build_system(repo_path: Path) -> str:
    if (repo_path / "pom.xml").exists():
        return "maven"
    if (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists():
        return "gradle"
    if (repo_path / "package.json").exists():
        return "npm"
    return "unknown"


def read_build_file(repo_path: Path, build_system: str) -> str:
    targets = {
        "maven": ["pom.xml"],
        "gradle": ["build.gradle", "build.gradle.kts"],
        "npm": ["package.json", "package-lock.json"],
    }
    content = ""
    for fname in targets.get(build_system, []):
        fpath = repo_path / fname
        if fpath.exists():
            try:
                content += fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    # Also check submodule build files (one level deep)
    for child in repo_path.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            for fname in targets.get(build_system, []):
                fpath = child / fname
                if fpath.exists():
                    try:
                        content += fpath.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        pass
    return content


def scan_for_docker_compose(repo_path: Path) -> list[str]:
    found = []
    for f in repo_path.rglob("docker-compose*.yml"):
        found.append(str(f.relative_to(repo_path)))
    for f in repo_path.rglob("docker-compose*.yaml"):
        found.append(str(f.relative_to(repo_path)))
    return found


def detect_infra(repo_path: Path, build_system: str, build_content: str) -> dict:
    detected = {}
    docker_files = scan_for_docker_compose(repo_path)

    for name, sig in INFRA_SIGNATURES.items():
        found = False
        # Check build file patterns
        for pattern in sig.get(build_system, []):
            if re.search(pattern, build_content, re.IGNORECASE):
                found = True
                break
        # Check for file-based indicators
        if not found:
            for file_hint in sig.get("files", []):
                for dc in docker_files:
                    if file_hint in dc.lower():
                        found = True
                        break
                if found:
                    break
        if found:
            detected[name] = {
                "capability": sig["capability"],
                "description": sig["description"],
            }
    return detected


def detect_external_deps(build_system: str, build_content: str) -> dict:
    detected = {}
    for name, dep in EXTERNAL_DEPS.items():
        for pattern in dep.get(build_system, []):
            if re.search(pattern, build_content, re.IGNORECASE):
                detected[name] = dep["service"]
                break
    return detected


def compute_coverage(infra: dict, deps: dict) -> dict:
    """Determine which external deps are coverable by detected infra."""
    coverable = {}
    coverage_map = {
        "postgresql": ["testcontainers", "embedded_db"],
        "redis": ["testcontainers", "embedded_redis"],
        "elasticsearch": ["testcontainers"],
        "sqs": ["localstack", "testcontainers"],
        "s3": ["localstack", "testcontainers"],
        "kafka": ["testcontainers"],
    }
    for dep_name, service in deps.items():
        covers = coverage_map.get(dep_name, [])
        covered_by = [c for c in covers if c in infra]
        coverable[dep_name] = {
            "service": service,
            "covered": len(covered_by) > 0,
            "covered_by": covered_by,
            "requires_real_infra": len(covered_by) == 0,
        }
    return coverable


def classify_max_capability(infra: dict) -> str:
    caps = [v["capability"] for v in infra.values()]
    if "INFRA_INTEGRATION" in caps:
        return "INFRA_INTEGRATION"
    if "MOCK_INTEGRATION" in caps:
        return "MOCK_INTEGRATION"
    return "UNIT_ONLY"


def run(repo_path_str: str, fmt: str = "json") -> str:
    repo_path = Path(repo_path_str).resolve()
    if not repo_path.is_dir():
        return json.dumps({"error": f"Not a directory: {repo_path}"})

    build_system = detect_build_system(repo_path)
    build_content = read_build_file(repo_path, build_system) if build_system != "unknown" else ""
    infra = detect_infra(repo_path, build_system, build_content)
    deps = detect_external_deps(build_system, build_content)
    coverage = compute_coverage(infra, deps)
    max_cap = classify_max_capability(infra)
    docker_files = scan_for_docker_compose(repo_path)

    uncovered = [k for k, v in coverage.items() if v["requires_real_infra"]]

    result = {
        "repo": str(repo_path),
        "build_system": build_system,
        "max_test_capability": max_cap,
        "test_infra": infra,
        "external_dependencies": deps,
        "coverage": coverage,
        "uncovered_dependencies": uncovered,
        "docker_compose_files": docker_files,
        "qa_guidance": _build_guidance(max_cap, infra, uncovered),
    }

    if fmt == "text":
        return _format_text(result)
    return json.dumps(result, indent=2)


def _build_guidance(max_cap: str, infra: dict, uncovered: list) -> dict:
    guidance = {
        "verifiable_locally": [],
        "not_verifiable_locally": [],
        "recommended_test_types": [],
    }

    if max_cap == "UNIT_ONLY":
        guidance["verifiable_locally"] = ["Pure logic", "Data transformations", "Validation rules"]
        guidance["not_verifiable_locally"] = ["Any external service interaction"]
        guidance["recommended_test_types"] = ["UNIT"]
    elif max_cap == "MOCK_INTEGRATION":
        guidance["verifiable_locally"] = [
            "Pure logic", "Data transformations", "Validation rules",
            "Repository layer (embedded DB)", "Controller layer (MockMvc/supertest)",
            "HTTP client behavior (WireMock/nock)",
        ]
        guidance["not_verifiable_locally"] = [f"Real {dep} interaction" for dep in uncovered]
        guidance["recommended_test_types"] = ["UNIT", "MOCK_INTEGRATION"]
    else:  # INFRA_INTEGRATION
        guidance["verifiable_locally"] = [
            "Pure logic", "Data transformations", "Validation rules",
            "Repository layer", "Controller layer",
            "Service-to-DB integration (Testcontainers)",
        ]
        if "localstack" in infra:
            guidance["verifiable_locally"].append("AWS service integration (LocalStack)")
        guidance["not_verifiable_locally"] = [f"Real {dep} interaction" for dep in uncovered]
        guidance["recommended_test_types"] = ["UNIT", "MOCK_INTEGRATION", "INFRA_INTEGRATION"]

    return guidance


def _format_text(result: dict) -> str:
    lines = [
        f"Repo: {result['repo']}",
        f"Build: {result['build_system']}",
        f"Max capability: {result['max_test_capability']}",
        "",
        "Test infra detected:",
    ]
    for name, info in result["test_infra"].items():
        lines.append(f"  [Y] {name}: {info['description']}")
    if not result["test_infra"]:
        lines.append("  (none)")
    lines.append("")
    lines.append("External dependencies:")
    for name, service in result["external_dependencies"].items():
        cov = result["coverage"].get(name, {})
        status = "[Y] covered" if cov.get("covered") else "[!] NOT covered locally"
        lines.append(f"  {name}: {service} -- {status}")
    if not result["external_dependencies"]:
        lines.append("  (none detected)")
    lines.append("")
    lines.append("QA guidance:")
    lines.append(f"  Recommended test types: {', '.join(result['qa_guidance']['recommended_test_types'])}")
    if result["qa_guidance"]["not_verifiable_locally"]:
        lines.append("  NOT verifiable locally:")
        for item in result["qa_guidance"]["not_verifiable_locally"]:
            lines.append(f"    [!] {item}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Detect test infrastructure in a repo")
    parser.add_argument("--repo", required=True, help="Path to repository root")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()
    print(run(args.repo, args.format))


if __name__ == "__main__":
    main()
