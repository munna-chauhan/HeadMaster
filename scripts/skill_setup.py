#!/usr/bin/env python
"""Single-call skill setup — returns all config + loop state as JSON.

Usage: python scripts/skill_setup.py <slug>

Replaces the 4-step Setup section that every skill repeats:
  1. Read config.yml
  2. Read loop_state.json
  3. Verify workflow .yml exists
  4. Extract project, tier, gates, etc.

Returns JSON printed to stdout. On fatal error: JSON with "error" key set
and exit code 1. Skills should HALT if "error" is non-null.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def main() -> None:
    # --config-only: validate config.yml + active project root only (used by init-feature Step 1)
    if "--config-only" in sys.argv:
        try:
            from config_utils import ConfigResolver
            resolver = ConfigResolver(REPO_ROOT / "config.yml")
            project = resolver.active_project
            root = resolver.get("root", None)
            if not project or project == "default":
                print(json.dumps({"error": "config.yml: projects.active not set"}))
                sys.exit(1)
            if not root:
                print(json.dumps({"error": f"config.yml: projects.{project}.root not defined"}))
                sys.exit(1)
            print(json.dumps({"ok": True, "project": project, "root": root}))
        except FileNotFoundError:
            print(json.dumps({"error": "config.yml not found"}))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
        sys.exit(0)

    slug = sys.argv[1] if len(sys.argv) > 1 else ""
    if not slug:
        print(json.dumps({"error": "slug argument required"}))
        sys.exit(1)

    # Load config
    try:
        from config_utils import ConfigResolver
        resolver = ConfigResolver(REPO_ROOT / "config.yml")
    except FileNotFoundError:
        print(json.dumps({"error": "config.yml not found — HALT"}))
        sys.exit(1)

    project = resolver.active_project
    project_key = resolver.get("project_key", "")
    jira_push = bool(resolver.get("jira_push", False))
    autonomous = bool(resolver.config.get("autonomous", False))

    pipeline = resolver.get_pipeline_config()
    max_loops = int(pipeline.get("max_loops", 3))
    parallel = bool(pipeline.get("parallel", False))

    # Gates (plan/design/breakdown/execute)
    gates_raw = resolver.config.get("gates", {})
    gates = {
        phase: {
            "interactive": bool(cfg.get("interactive", True)),
            "review_mode": cfg.get("review", {}).get("mode", "human_in_loop"),
        }
        for phase, cfg in gates_raw.items()
        if isinstance(cfg, dict)
    }

    # Loop state
    memory_path = REPO_ROOT / "memory" / "features" / project / slug
    loop_state_path = memory_path / "loop_state.json"

    if not loop_state_path.exists():
        print(json.dumps({"error": f"loop_state.json not found. Run /init-feature first."}))
        sys.exit(1)

    try:
        loop_state = json.loads(loop_state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"error": f"loop_state.json corrupt: {e}"}))
        sys.exit(1)

    tier = loop_state.get("complexity_tier", loop_state.get("tier")) or None

    # Verify workflow file exists — spike/research routes use workflow field instead of tier
    workflow_key = tier if tier else loop_state.get("workflow", "m")
    workflow_file = REPO_ROOT / ".claude" / "workflows" / f"{workflow_key}.yml"
    if not workflow_file.exists():
        print(json.dumps({"error": f"Workflow file not found: .claude/workflows/{workflow_key}.yml"}))
        sys.exit(1)

    print(json.dumps({
        "project": project,
        "project_key": project_key,
        "slug": slug,
        "tier": tier,
        "workflow": workflow_key,
        "max_loops": max_loops,
        "parallel": parallel,
        "jira_push": jira_push,
        "autonomous": autonomous,
        "gates": gates,
        "workflow_file": f".claude/workflows/{workflow_key}.yml",
        "loop_state_path": str(loop_state_path),
        "docs_path": str(REPO_ROOT / "docs" / "features" / project / slug),
        "memory_path": str(memory_path),
        "error": None,
    }, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
