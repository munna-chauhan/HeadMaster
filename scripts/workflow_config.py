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
"""
workflow_config.py — Read tier workflow definitions from .claude/workflows/{tier}.yml

Two interfaces:
  1. Python import:  from scripts.workflow_config import get, get_stages, get_sections
  2. CLI:            sh scripts/workflow_config.py <tier> <dotpath>

Examples:
  sh scripts/workflow_config.py s stages.prd.sections
  sh scripts/workflow_config.py xs stages.tdd.artifact
  sh scripts/workflow_config.py m escalation_thresholds.story_count
  sh scripts/workflow_config.py l stages.system_design.status
  sh scripts/workflow_config.py classification algorithm
  sh scripts/workflow_config.py reclassification rework.s_to_m
  sh scripts/workflow_config.py stage-skip-rules rules.discovery.skip_if
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    # Inline minimal YAML parser for environments without PyYAML
    yaml = None

REPO_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".claude" / "workflows"

# Tier files
TIER_FILES = {"xs", "s", "m", "l"}
# Non-tier workflow files
OTHER_FILES = {"classification", "reclassification", "stage-skip-rules"}


def _load_yml(name: str) -> dict:
    """Load a workflow yml file by name (without extension)."""
    path = WORKFLOWS_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    text = path.read_text(encoding="utf-8")

    if yaml:
        return yaml.safe_load(text) or {}

    # Fallback: minimal YAML-like parser for simple key-value structures
    # Only handles the subset used by workflow files
    import re
    result = {}
    current_key = None
    current_list = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current_list is not None:
                current_list.append(stripped[2:].strip().strip('"').strip("'"))
            continue

        m = re.match(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)', line)
        if m:
            indent = len(m.group(1))
            key = m.group(2)
            val = m.group(3).strip().strip('"').strip("'")

            if val == "" or val == "|":
                # Could be a dict or list parent
                current_key = key
                current_list = []
                result[key] = current_list
            else:
                result[key] = val
                current_list = None

    return result


def _resolve_dotpath(data: dict, dotpath: str):
    """Resolve a dot-separated path into nested dict/list."""
    keys = dotpath.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            if key not in current:
                return None
            current = current[key]
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def get(tier_or_file: str, dotpath: str = None):
    """
    Get a value from a workflow file.

    Args:
        tier_or_file: tier name (xs/s/m/l) or file name (classification/reclassification/stage-skip-rules)
        dotpath: dot-separated path to value (e.g., "stages.prd.sections")

    Returns:
        The value at the path, or the entire file dict if no dotpath.
    """
    data = _load_yml(tier_or_file)
    if dotpath is None:
        return data
    return _resolve_dotpath(data, dotpath)


def get_stages(tier: str) -> dict:
    """Get all stages for a tier with their status/agent/artifact/sections."""
    return get(tier, "stages") or {}


def get_sections(tier: str, stage: str) -> list:
    """Get section list for a specific stage in a tier. Returns [] if stage is skip."""
    result = get(tier, f"stages.{stage}.sections")
    return result if isinstance(result, list) else []


def get_status(tier: str, stage: str) -> str:
    """Get stage status: required, optional, or skip."""
    result = get(tier, f"stages.{stage}.status")
    return str(result) if result else "skip"


def get_artifact(tier: str, stage: str) -> str:
    """Get artifact name for a stage. Returns None if stage is skip."""
    return get(tier, f"stages.{stage}.artifact")


def get_gate(tier: str, stage: str) -> str:
    """Get gate condition for a stage. Returns None if no gate."""
    return get(tier, f"stages.{stage}.gate")


def get_escalation_thresholds(tier: str) -> dict:
    """Get escalation thresholds for a tier. Returns {} for l (no escalation)."""
    return get(tier, "escalation_thresholds") or {}


def get_skip_rules(stage: str) -> dict:
    """Get skip rules for an optional stage."""
    return get("stage-skip-rules", f"rules.{stage}") or {}


def get_classification() -> dict:
    """Get full classification config."""
    return get("classification") or {}


def get_reclassification() -> dict:
    """Get full reclassification config."""
    return get("reclassification") or {}


def get_rework(from_tier: str, to_tier: str) -> list:
    """Get rework rules for a tier transition. Returns [] if no rework needed."""
    if from_tier == to_tier:
        return []
    key = f"{from_tier}_to_{to_tier}"
    result = get("reclassification", f"rework.{key}")
    if result:
        return result if isinstance(result, list) else [result]
    # Check downgrade
    result = get("reclassification", "rework.downgrade")
    return result if isinstance(result, list) else [str(result)] if result else []


# ─────────────────────────────────────────────────────────────────────────────
# CLI interface
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: sh scripts/workflow_config.py <tier|file> [dotpath]", file=sys.stderr)
        print("  Tiers: xs, s, m, l", file=sys.stderr)
        print("  Files: classification, reclassification, stage-skip-rules", file=sys.stderr)
        print("  Example: sh scripts/workflow_config.py s stages.prd.sections", file=sys.stderr)
        sys.exit(1)

    tier_or_file = sys.argv[1]
    dotpath = sys.argv[2] if len(sys.argv) > 2 else None

    if tier_or_file not in TIER_FILES and tier_or_file not in OTHER_FILES:
        print(f"Unknown tier/file: {tier_or_file}", file=sys.stderr)
        print(f"Valid: {', '.join(sorted(TIER_FILES | OTHER_FILES))}", file=sys.stderr)
        sys.exit(1)

    try:
        result = get(tier_or_file, dotpath)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if result is None:
        print(f"Path not found: {dotpath}", file=sys.stderr)
        sys.exit(1)

    # Output format: list → one item per line, dict → JSON, scalar → plain
    if isinstance(result, list):
        for item in result:
            if isinstance(item, (dict, list)):
                sys.stdout.buffer.write((json.dumps(item) + "\n").encode("utf-8"))
            else:
                sys.stdout.buffer.write((str(item) + "\n").encode("utf-8"))
    elif isinstance(result, dict):
        sys.stdout.buffer.write((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    else:
        sys.stdout.buffer.write((str(result) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
