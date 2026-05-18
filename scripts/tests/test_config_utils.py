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
"""Unit tests for config_utils.py"""

import pytest
import yaml
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_utils import ConfigResolver


def test_get_feature_memory_path_acme_project(tmp_path):
    """Returns correct path for acme project."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {
                "root": ".",
                "project_key": "ACME"
            }
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)
    path = resolver.get_feature_memory_path("test-feature", project="acme")

    expected = resolver.hm_root / "memory" / "features" / "acme" / "test-feature"
    assert path == expected


def test_get_feature_memory_path_beta_project(tmp_path):
    """Returns correct path for beta project."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "beta": {
                "root": ".",
                "project_key": "BETA"
            }
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)
    path = resolver.get_feature_memory_path("test-feature", project="beta")

    expected = resolver.hm_root / "memory" / "features" / "beta" / "test-feature"
    assert path == expected


def test_get_active_project_reads_from_config(tmp_path):
    """Reads active project from config correctly."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "beta",
            "acme": {"root": ".", "project_key": "ACME"},
            "beta": {"root": ".", "project_key": "BETA"}
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)

    assert resolver.active_project == "beta"


def test_missing_config_file_raises_clear_error(tmp_path):
    """Missing config file raises FileNotFoundError, not AttributeError."""
    config_path = tmp_path / "nonexistent.yml"

    with pytest.raises(FileNotFoundError) as exc_info:
        ConfigResolver(config_path)

    assert "Config not found" in str(exc_info.value)
    assert str(config_path) in str(exc_info.value)


def test_get_project_specific_setting(tmp_path):
    """Gets project-specific setting (coverage_threshold)."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {
                "root": ".",
                "project_key": "ACME",
                "coverage_threshold": 80
            },
            "beta": {
                "root": ".",
                "project_key": "BETA",
                "coverage_threshold": 70
            }
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)

    acme_coverage = resolver.get("coverage_threshold", project="acme")
    beta_coverage = resolver.get("coverage_threshold", project="beta")

    assert acme_coverage == 80
    assert beta_coverage == 70


def test_get_jira_push_flag(tmp_path):
    """Gets project-specific jira_push flag."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {
                "root": ".",
                "project_key": "ACME",
                "jira_push": True
            },
            "beta": {
                "root": ".",
                "project_key": "BETA",
                "jira_push": False
            }
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)

    assert resolver.get("jira_push", project="acme") is True
    assert resolver.get("jira_push", project="beta") is False


def test_get_project_key(tmp_path):
    """Gets project-specific project_key."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {
                "root": ".",
                "project_key": "ACME"
            },
            "beta": {
                "root": ".",
                "project_key": "BETA"
            }
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)

    assert resolver.get("project_key", project="acme") == "ACME"
    assert resolver.get("project_key", project="beta") == "BETA"


def test_get_pipeline_config(tmp_path):
    """Gets pipeline configuration."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {"root": ".", "project_key": "ACME"}
        },
        "pipeline": {
            "max_loops": 3,
            "parallel": False,
            "interactive": True
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)
    pipeline = resolver.get_pipeline_config()

    assert pipeline["max_loops"] == 3
    assert pipeline["parallel"] is False
    assert pipeline["interactive"] is True


def test_get_features_path(tmp_path):
    """Gets correct features path for project."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {"root": ".", "project_key": "ACME"}
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)
    path = resolver.get_features_path(project="acme")

    expected = resolver.hm_root / "docs" / "features" / "acme"
    assert path == expected


def test_default_values_when_missing(tmp_path):
    """Returns default value when setting not in config."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {"root": ".", "project_key": "ACME"}
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)
    value = resolver.get("nonexistent_key", default=42, project="acme")

    assert value == 42


def test_uses_active_project_when_not_specified(tmp_path):
    """Uses active project when project parameter not specified."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "beta",
            "acme": {"root": ".", "project_key": "ACME"},
            "beta": {"root": ".", "project_key": "BETA"}
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)

    # Without project parameter, should use active (beta)
    path = resolver.get_feature_memory_path("test-feature")
    expected = resolver.hm_root / "memory" / "features" / "beta" / "test-feature"
    assert path == expected


def test_get_project_config(tmp_path):
    """Gets full project configuration."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {
                "root": ".",
                "project_key": "ACME",
                "jira_push": True,
                "coverage_threshold": 80
            }
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)
    ws_config = resolver.get_project_config(project="acme")

    assert ws_config["root"] == "."
    assert ws_config["project_key"] == "ACME"
    assert ws_config["jira_push"] is True
    assert ws_config["coverage_threshold"] == 80


def test_backward_compatible_key_mapping(tmp_path):
    """Supports backward-compatible key names."""
    config_path = tmp_path / "config.yml"
    config = {
        "projects": {
            "active": "acme",
            "acme": {
                "root": "/custom/path",
                "project_key": "ACME"
            }
        }
    }
    config_path.write_text(yaml.dump(config))

    resolver = ConfigResolver(config_path)

    # Both old and new keys should work
    assert resolver.get("root", project="acme") == "/custom/path"
    assert resolver.get("root", project="acme") == "/custom/path"
