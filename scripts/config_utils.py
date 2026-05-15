#!/usr/bin/env python
"""
Config resolution utilities for HeadMaster scripts.
Handles new hierarchical config.yml structure with project overrides.
"""

import yaml
from pathlib import Path
from typing import Any, Optional
CONFIG_PROJECTS_KEY = "projects"
CONFIG_ACTIVE_KEY = "active"

ALLOWED_TOP_LEVEL_KEYS = {"projects", "pipeline", "autonomous", "gates", "security"}


class ConfigResolver:
    """Resolves config values with project override support."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.active_project = self._get_active_project()
        self.hm_root = Path(__file__).parent.parent  # HeadMaster root

    def _get_active_project(self) -> str:
        """Get active project slug."""
        return self.config.get(CONFIG_PROJECTS_KEY, {}).get(CONFIG_ACTIVE_KEY, "default")

    def get_features_path(self, project: Optional[str] = None) -> Path:
        """Get features path for project: docs/features/{project}/"""
        proj_slug = project or self.active_project
        return self.hm_root / "docs" / "features" / proj_slug

    def get_feature_memory_path(self, slug: str, project: Optional[str] = None) -> Path:
        """Get feature memory path: memory/features/{project}/{slug}/"""
        proj_slug = project or self.active_project
        return self.hm_root / "memory" / "features" / proj_slug / slug

    def get(self, key: str, default: Any = None, project: Optional[str] = None) -> Any:
        """
        Get config value. Resolution order:
        1. project-specific override
        2. top-level key
        3. provided default
        """
        proj_slug = project or self.active_project

        projects = self.config.get(CONFIG_PROJECTS_KEY, {})
        if proj_slug in projects and key in projects[proj_slug]:
            return projects[proj_slug][key]

        if key in self.config:
            return self.config[key]

        return default

    def get_project_config(self, project: Optional[str] = None) -> dict:
        """Get full project configuration."""
        proj_slug = project or self.active_project
        projects = self.config.get(CONFIG_PROJECTS_KEY, {})
        return projects.get(proj_slug, {})

    def get_pipeline_config(self) -> dict:
        """Get pipeline configuration."""
        return self.config.get("pipeline", {})

    def validate(self) -> list[str]:
        """Return list of unknown top-level keys (not in ALLOWED_TOP_LEVEL_KEYS)."""
        return [k for k in self.config if k not in ALLOWED_TOP_LEVEL_KEYS]


# Convenience functions for backward compatibility
def load_config(config_path: Optional[Path] = None) -> ConfigResolver:
    """Load config and return resolver."""
    return ConfigResolver(config_path)


def get_project_root(resolver: ConfigResolver, project: Optional[str] = None) -> str:
    """Get project root path."""
    return resolver.get("root", ".", project)


def get_project_key(resolver: ConfigResolver, project: Optional[str] = None) -> str:
    """Get project key."""
    return resolver.get("project_key", "HeadMaster", project)


def get_jira_push_enabled(resolver: ConfigResolver, project: Optional[str] = None) -> bool:
    """Check if Jira push is enabled."""
    return resolver.get("jira_push", False, project)


if __name__ == "__main__":
    import sys

    _USAGE = (
        "Usage: config_utils.py <command> [args]\n"
        "Commands:\n"
        "  get <dotted.key>                     → value or empty string\n"
        "  feature-memory-path <project> <slug> → absolute path\n"
        "  features-path [project]              → absolute path\n"
        "  active-project                       → project slug\n"
        "  validate [config.yml]                → exit 0 if clean, 1 if unknown keys\n"
    )

    if len(sys.argv) < 2:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "validate":
        config_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
        try:
            r = ConfigResolver(config_path)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        unknown = r.validate()
        if unknown:
            print(f"Unknown config keys: {', '.join(unknown)}", file=sys.stderr)
            sys.exit(1)
        print("ok")
        sys.exit(0)

    resolver = ConfigResolver()

    if cmd == "get":
        if len(sys.argv) < 3:
            print("get requires <key>", file=sys.stderr)
            sys.exit(1)
        key = sys.argv[2]
        # Traverse dotted keys directly in raw config first
        parts = key.split(".")
        val: Any = resolver.config
        for part in parts:
            val = val.get(part) if isinstance(val, dict) else None
        if val is not None:
            print(val)
        else:
            # Fall back to project-aware resolver
            result = resolver.get(key, "")
            if result != "":
                print(result)

    elif cmd == "feature-memory-path":
        if len(sys.argv) < 4:
            print("feature-memory-path requires <project> <slug>", file=sys.stderr)
            sys.exit(1)
        print(resolver.get_feature_memory_path(sys.argv[3], sys.argv[2]))

    elif cmd == "features-path":
        project = sys.argv[2] if len(sys.argv) > 2 else None
        print(resolver.get_features_path(project))

    elif cmd == "active-project":
        print(resolver.active_project)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
