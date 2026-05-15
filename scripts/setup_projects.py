#!/usr/bin/env python
"""
Resolve project paths from config.yml into:
  1. docs/features/{project}/ + memory/features/{project}/   (per-project work dirs)
  2. .claude/settings.local.json                              (Claude Code overrides)

settings.local.json is gitignored — per-machine. Holds:
  - additionalDirectories: every project root (so Read works across repos)
  - Write allow/deny scoped to each project root

Run after editing config.yml. Idempotent.

Usage:
    python scripts/setup_projects.py
"""

import json
from pathlib import Path

import yaml

HM_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = HM_ROOT / "config.yml"
LOCAL_SETTINGS = HM_ROOT / ".claude" / "settings.local.json"


def _load_projects() -> dict:
    if not CONFIG_PATH.exists():
        print(f"[ERROR] {CONFIG_PATH} not found")
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("projects", {}) or {}


def _resolve_root(root: str) -> str:
    """Project root may be relative to HeadMaster or absolute. Return absolute."""
    p = Path(root)
    if not p.is_absolute():
        p = (HM_ROOT / root).resolve()
    return str(p)


def _ensure_work_dirs(slug: str) -> None:
    (HM_ROOT / "docs" / "features" / slug).mkdir(parents=True, exist_ok=True)
    (HM_ROOT / "memory" / "features" / slug).mkdir(parents=True, exist_ok=True)


def _write_local_settings(roots: list[str]) -> None:
    """Generate settings.local.json with per-project paths. Preserves any
    existing local overrides outside the managed keys."""
    existing: dict = {}
    if LOCAL_SETTINGS.exists():
        try:
            existing = json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    perms = existing.get("permissions", {})
    allow = [r for r in perms.get("allow", []) if not r.startswith("Write(")]
    deny = [r for r in perms.get("deny", []) if not r.startswith("Write(")]

    for root in roots:
        allow.append(f"Write({root}/**)")
        deny.extend([
            f"Write({root}/**/.env*)",
            f"Write({root}/**/secrets.*)",
            f"Write({root}/**/application-prod.*)",
        ])

    perms["allow"] = allow
    perms["deny"] = deny
    perms["additionalDirectories"] = roots
    existing["permissions"] = perms

    LOCAL_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_SETTINGS.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def setup_projects() -> bool:
    projects = _load_projects()
    if not projects:
        print("[INFO] No projects defined in config.yml")
        return False

    work_dirs: list[str] = []
    roots: list[str] = []
    for slug, entry in projects.items():
        if slug == "active":
            continue
        if not isinstance(entry, dict):
            continue
        _ensure_work_dirs(slug)
        work_dirs.append(slug)

        root = entry.get("root")
        if root:
            resolved = _resolve_root(root)
            if Path(resolved).exists():
                roots.append(resolved)
            else:
                print(f"[WARN] project '{slug}' root not found: {resolved}")

    if work_dirs:
        print(f"[OK] work dirs ready: {', '.join(work_dirs)}")

    if roots:
        _write_local_settings(roots)
        print(f"[OK] {LOCAL_SETTINGS.relative_to(HM_ROOT)} updated ({len(roots)} root(s))")

    return True


if __name__ == "__main__":
    setup_projects()
