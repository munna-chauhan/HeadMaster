#!/usr/bin/env python
"""
Auto-create project directory structure from config.yml

Reads all projects defined in config.yml and creates:
- docs/features/{project}/
- memory/features/{project}/

Usage:
    python scripts/setup_projects.py
"""

import yaml
from pathlib import Path


def setup_projects():
    """Create project directories from config.yml"""
    config_path = Path(__file__).parent.parent / "config.yml"

    if not config_path.exists():
        print("[ERROR] config.yml not found")
        return False

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    projects = config.get("projects", {})
    created = []

    for slug in projects.keys():
        if slug == "active":
            continue

        # Create docs/features/{project}/
        docs_path = Path("docs/features") / slug
        docs_path.mkdir(parents=True, exist_ok=True)

        # Create memory/features/{project}/
        memory_path = Path("memory/features") / slug
        memory_path.mkdir(parents=True, exist_ok=True)

        created.append(slug)

    if created:
        print(f"[OK] Project directories created for: {', '.join(created)}")
        print(f"     docs/features/{{project}}/")
        print(f"     memory/features/{{project}}/")
    else:
        print("[INFO] No projects found in config.yml")

    return True


if __name__ == "__main__":
    setup_projects()
