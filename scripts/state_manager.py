#!/usr/bin/env python
"""Pipeline state management — single module for loop_state.json operations.

Public API:
  detect_phase(project, slug, project_dir)  -> (phase, stage, hint)
  validate_loop_state(path)                  -> (is_valid, error_msg)
  format_validation_error(project, slug, msg) -> str
  tdd_breakdown_pairs(artifacts)             -> list[dict]

CLI:
  python scripts/state_manager.py --project <p> --slug <s> [--project-dir <dir>]
  python scripts/state_manager.py --validate <path>
  python scripts/state_manager.py --status [--project <p>]
  python scripts/state_manager.py --rebuild --project <p> --slug <s>
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_ROUTES        = {"spike", "hotfix", "feature", "epic"}
VALID_TIERS         = {"xs", "s", "m", "l"}
VALID_WORKFLOWS     = {"research", "xs", "s", "m", "l"}
VALID_PIPELINE_MODES= {"full", "skip-plan", "skip-to-execute", "plan-only"}
VALID_PHASES        = {"planning", "design", "breakdown", "execute"}
VALID_STORY_STATUS  = {"NEW", "IN_PROGRESS", "SCANNING", "IN_REVIEW", "IN_QA",
                       "COMPLETE", "DEFERRED", "BLOCKED"}
VALID_PHASE_CODES   = {"A", "B", "C"}
REQUIRED_KEYS       = {"feature_slug", "route", "workflow", "pipeline_mode"}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_loop_state(path: Path) -> Tuple[bool, Optional[str]]:
    """Validate loop_state.json. Returns (is_valid, error_message)."""
    if not path.exists():
        return True, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Malformed JSON: {e}"
    except Exception as e:
        return False, f"Read error: {e}"

    missing = REQUIRED_KEYS - set(state.keys())
    if missing:
        return False, f"Missing required keys: {missing}"

    route = state.get("route")
    if route not in VALID_ROUTES:
        return False, f"Invalid route: {route} (valid: {VALID_ROUTES})"

    workflow = state.get("workflow")
    if workflow not in VALID_WORKFLOWS:
        return False, f"Invalid workflow: {workflow} (valid: {VALID_WORKFLOWS})"

    mode = state.get("pipeline_mode")
    if mode not in VALID_PIPELINE_MODES:
        return False, f"Invalid pipeline_mode: {mode} (valid: {VALID_PIPELINE_MODES})"

    tier = state.get("complexity_tier")
    if tier is not None and tier not in VALID_TIERS:
        return False, f"Invalid complexity_tier: {tier} (valid: {VALID_TIERS} or null)"

    if route == "spike":
        if workflow != "research":
            return False, f"Spike route must use research workflow, got: {workflow}"
        if tier is not None:
            return False, f"Spike route must have null tier at init, got: {tier}"
        if mode != "plan-only":
            return False, f"Spike route must use plan-only mode, got: {mode}"

    pipeline = state.get("pipeline")
    if pipeline is not None:
        if not isinstance(pipeline, dict):
            return False, "pipeline must be a dict"
        phase = pipeline.get("phase")
        if phase and phase not in VALID_PHASES:
            return False, f"Invalid pipeline phase: {phase} (valid: {VALID_PHASES})"

    stories = state.get("stories")
    if stories is not None:
        if not isinstance(stories, dict):
            return False, "stories must be a dict"
        for story_id, story_data in stories.items():
            if not isinstance(story_data, dict):
                return False, f"Story {story_id} must be a dict"
            status = story_data.get("status")
            if status and status not in VALID_STORY_STATUS:
                return False, f"Story {story_id} invalid status: {status}"
            phases_completed = story_data.get("phases_completed")
            if phases_completed is not None:
                if not isinstance(phases_completed, list):
                    return False, f"Story {story_id} phases_completed must be a list"
                invalid = set(phases_completed) - VALID_PHASE_CODES
                if invalid:
                    return False, f"Story {story_id} invalid phase codes: {invalid}"

    return True, None


def format_validation_error(project: str, slug: str, error_msg: str) -> str:
    return (
        f"CORRUPTED STATE: {project}/{slug}\n"
        f"Error: {error_msg}\n"
        f"Recover: python scripts/cleanup_failed_run.py {project} {slug} --reset-state\n"
        f"Then: /navigate {slug}"
    )


# ---------------------------------------------------------------------------
# Artifact helpers
# ---------------------------------------------------------------------------

def tdd_breakdown_pairs(artifacts: dict) -> list:
    """Return TDD↔breakdown pairing derived from naming convention.

    For each design/TDD_{NAME}.md entry (excluding TDD_MASTER.md),
    derives the corresponding breakdown/JIRA_BREAKDOWN_{NAME}.md path
    and returns both statuses. Skills use this to determine what's
    pending without reading any files.
    """
    pairs = []
    for path, meta in artifacts.items():
        if not path.startswith("design/TDD_"):
            continue
        if path.endswith("_MASTER.md") or path == "design/TDD.md":
            continue
        name = path.removeprefix("design/TDD_").removesuffix(".md")
        bd_path = f"breakdown/JIRA_BREAKDOWN_{name}.md"
        pairs.append({
            "name":             name,
            "tdd":              path,
            "tdd_status":       meta.get("status"),
            "breakdown":        bd_path,
            "breakdown_status": artifacts.get(bd_path, {}).get("status", "pending"),
        })
    return pairs


# ---------------------------------------------------------------------------
# Phase detection
# ---------------------------------------------------------------------------

def _read_loop_state(project: str, slug: str, project_dir: str) -> Optional[dict]:
    path = os.path.join(project_dir, "memory", "features", project, slug, "loop_state.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        import sys
        print(f"state_manager: error reading {path}: {e}", file=sys.stderr)
        return None


def detect_phase(project: str, slug: str, project_dir: str = None) -> Tuple[str, str, str]:
    """Detect current phase/stage. Returns (phase, stage, hint).

    Priority:
      1. loop_state pipeline key  (explicit state from gate_transition)
      2. loop_state artifacts key (derived from artifact statuses — no file reads)
      3. loop_state stories key   (execution progress)
      4. Filesystem scan          (fallback for old features without artifacts key)
    """
    if project_dir is None:
        project_dir = os.getcwd()

    state = _read_loop_state(project, slug, project_dir)

    if state:
        # Priority 1: explicit pipeline state
        pipeline = state.get("pipeline")
        if pipeline and "phase" in pipeline and "stage" in pipeline:
            phase, stage = pipeline["phase"], pipeline["stage"]
            return phase, stage, _hint_from_phase(phase, slug)

        # Priority 2+3: derive from artifacts + stories
        artifacts = state.get("artifacts")
        stories   = state.get("stories")
        if artifacts:
            return _phase_from_state(artifacts, stories or {}, slug)

    # Priority 4: filesystem scan (no artifacts key yet)
    return _detect_phase_from_fs(project, slug, project_dir)


def _hint_from_phase(phase: str, slug: str) -> str:
    return {
        "planning":  f"Run /plan {slug}",
        "design":    f"Run /design {slug}",
        "breakdown": f"Run /breakdown {slug}",
        "execute":   f"Run /execute {slug}",
    }.get(phase, f"Run /navigate {slug}")


def _phase_from_state(artifacts: dict, stories: dict, slug: str) -> Tuple[str, str, str]:
    """Derive phase from artifacts dict + stories dict. No file reads."""

    # --- Execute phase: check story execution progress ---
    if stories:
        result = _phase_from_stories(stories, slug)
        if result:
            return result

    # --- Breakdown phase: any JIRA_BREAKDOWN file present ---
    bd_files = [p for p in artifacts if p.startswith("breakdown/JIRA_BREAKDOWN")]
    if bd_files:
        all_pushed_or_local = all(
            artifacts[p].get("status") in ("pushed", "local")
            for p in bd_files
        )
        if all_pushed_or_local:
            return "execute", "ready", f"Run /execute {slug}"
        return "breakdown", "ready", f"Run /breakdown {slug}"

    # --- Design phase: TDD files or SYSTEM_DESIGN_NOTES ---
    tdd_files = [p for p in artifacts if p.startswith("design/TDD")]
    sdn = artifacts.get("design/SYSTEM_DESIGN_NOTES.md", {})
    review = artifacts.get("design/TDD_REVIEW.md", {})

    if review.get("status") in ("APPROVED", "CONDITIONAL"):
        return "breakdown", "ready", f"Run /breakdown {slug}"

    if tdd_files:
        return "design", "Review", f"Run /design {slug}"

    if sdn.get("status") == "locked":
        return "design", "Engineer", f"Run /design {slug}"

    if sdn:
        return "design", "Architect", f"Run /design {slug}"

    # --- Planning phase ---
    prd = artifacts.get("planning/PRD.md", {})
    if prd.get("status") == "APPROVED":
        return "design", "Architect", f"Run /design {slug}"
    if prd:
        return "planning", "Review", f"Run /plan {slug}"

    return "planning", "Init", f"Run /plan {slug}"


def _phase_from_stories(stories: dict, slug: str) -> Optional[Tuple[str, str, str]]:
    """Derive execute sub-phase from stories dict. Returns None if not in execute."""
    if not stories:
        return None
    statuses = {s.get("status", "NEW") for s in stories.values()}
    active = {"IN_PROGRESS", "SCANNING", "IN_REVIEW", "IN_QA"}
    if statuses & active:
        return "execute", "in-progress", f"Run /execute {slug} (resume)"
    if statuses <= {"COMPLETE", "DEFERRED", "BLOCKED"} and "NEW" not in statuses:
        return "execute", "complete", f"Run /breakdown {slug} merge-gate"
    return None


# ---------------------------------------------------------------------------
# Filesystem fallback (legacy — no artifacts key)
# ---------------------------------------------------------------------------

def _detect_phase_from_fs(project: str, slug: str, project_dir: str) -> Tuple[str, str, str]:
    """Filesystem scan. Used only when loop_state.json has no artifacts key."""
    base     = os.path.join(project_dir, "docs", "features", project, slug)
    planning = os.path.join(base, "planning")
    design   = os.path.join(base, "design")
    breakdown= os.path.join(base, "breakdown")

    # Breakdown / execute
    import glob
    bd_files = glob.glob(os.path.join(breakdown, "JIRA_BREAKDOWN*.md"))
    if bd_files:
        return _breakdown_phase_from_fs(bd_files[0], slug)

    # Design — TDD review
    tdd_review = os.path.join(design, "TDD_REVIEW.md")
    if os.path.exists(tdd_review):
        try:
            head = open(tdd_review, "rb").read(500).decode("utf-8", errors="ignore")
            if "APPROVED" in head or "CONDITIONAL" in head:
                return "breakdown", "ready", f"Run /breakdown {slug}"
        except Exception:
            pass
        return "design", "Review", f"Run /design {slug}"

    # Design — SDN
    sdn = os.path.join(design, "SYSTEM_DESIGN_NOTES.md")
    if os.path.exists(sdn):
        try:
            size = os.path.getsize(sdn)
            tail = open(sdn, "rb").read()[-200:].decode("utf-8", errors="ignore") if size else ""
            if "Architecture Locked: YES" in tail:
                stage = "Review" if os.path.exists(tdd_review) else "Engineer"
                return "design", stage, f"Run /design {slug}"
        except Exception:
            pass
        return "design", "Architect", f"Run /design {slug}"

    # Planning — PRD
    prd = os.path.join(planning, "PRD.md")
    if os.path.exists(prd):
        try:
            size = os.path.getsize(prd)
            tail = open(prd, "rb").read()[-200:].decode("utf-8", errors="ignore") if size else ""
            if "PRD Status: APPROVED" in tail:
                return "design", "Architect", f"Run /design {slug}"
        except Exception:
            pass
        return "planning", "Review", f"Run /plan {slug}"

    # Planning — discovery
    discovery = os.path.join(planning, "DISCOVERY_NOTES.md")
    if os.path.exists(discovery):
        try:
            tail = open(discovery, "rb").read()[-100:].decode("utf-8", errors="ignore")
            stage = "Draft" if "All Questions Resolved: YES" in tail else "Discover"
        except Exception:
            stage = "Discover"
        return "planning", stage, f"Run /plan {slug}"

    if os.path.exists(os.path.join(planning, "FEATURE_DRAFT.md")):
        return "planning", "Discover", f"Run /plan {slug}"

    return "planning", "Init", f"Run /plan {slug}"


def _breakdown_phase_from_fs(jira_breakdown_path: str, slug: str) -> Tuple[str, str, str]:
    """Legacy: derive execute sub-phase by reading JIRA_BREAKDOWN content."""
    try:
        content = open(jira_breakdown_path, encoding="utf-8").read()
    except Exception:
        return "execute", "ready", f"Run /execute {slug}"
    if any(m in content for m in ["🔄 IN PROGRESS", "🔍 SCANNING", "👁️ IN REVIEW", "🧪 IN QA"]):
        return "execute", "in-progress", f"Run /execute {slug} (resume)"
    if "✅ COMPLETE" in content and "⏳ NEW" not in content:
        return "execute", "complete", f"Run /breakdown {slug} merge-gate"
    return "execute", "ready", f"Run /execute {slug}"


# ---------------------------------------------------------------------------
# Rebuild artifacts key from filesystem
# ---------------------------------------------------------------------------

def rebuild_artifacts(project: str, slug: str, repo_root: Path = None) -> dict:
    """Scan filesystem and reconstruct artifacts dict for loop_state.json.

    Infers status from file content markers. Use when artifacts key is missing
    or suspected to be out of sync.
    """
    repo_root = repo_root or REPO_ROOT
    base = repo_root / "docs" / "features" / project / slug
    artifacts = {}

    def _add(rel: str, status: str):
        artifacts[rel] = {"status": status}

    # PRD — status is in header table (top of file)
    prd = base / "planning" / "PRD.md"
    if prd.exists():
        try:
            head = prd.read_bytes()[:1500].decode("utf-8", errors="ignore")
            status = "APPROVED" if "APPROVED" in head else "draft"
        except Exception:
            status = "draft"
        _add("planning/PRD.md", status)

    # SDN — "Architecture Locked" line can be deep in a large file; scan last 1KB
    sdn = base / "design" / "SYSTEM_DESIGN_NOTES.md"
    if sdn.exists():
        try:
            tail = sdn.read_bytes()[-1000:].decode("utf-8", errors="ignore")
            status = "locked" if "Architecture Locked: YES" in tail else "draft"
        except Exception:
            status = "draft"
        _add("design/SYSTEM_DESIGN_NOTES.md", status)

    # TDD files
    for tdd_file in sorted((base / "design").glob("TDD*.md")):
        _add(f"design/{tdd_file.name}", "draft")

    # TDD_REVIEW
    tdd_review = base / "design" / "TDD_REVIEW.md"
    if tdd_review.exists():
        try:
            head = tdd_review.read_bytes()[:500].decode("utf-8", errors="ignore")
            if "APPROVED" in head:
                status = "APPROVED"
            elif "CONDITIONAL" in head:
                status = "CONDITIONAL"
            else:
                status = "draft"
        except Exception:
            status = "draft"
        _add("design/TDD_REVIEW.md", status)

    # JIRA_BREAKDOWN files
    for bd_file in sorted((base / "breakdown").glob("JIRA_BREAKDOWN*.md")):
        try:
            content = bd_file.read_text(encoding="utf-8")
            if "PUSHED TO JIRA" in content:
                status = "pushed"
            elif "LOCAL ONLY" in content:
                status = "local"
            else:
                status = "draft"
        except Exception:
            status = "draft"
        _add(f"breakdown/{bd_file.name}", status)

    return artifacts


# ---------------------------------------------------------------------------
# Feature status (read-only reporter)
# ---------------------------------------------------------------------------

def feature_status(project: str, slug: str, repo_root=None) -> Optional[dict]:
    """Return status dict for one feature, or None if loop_state missing."""
    repo_root = Path(repo_root or REPO_ROOT)
    memory_dir = repo_root / "memory" / "features" / project / slug
    loop_state_path = memory_dir / "loop_state.json"
    if not loop_state_path.exists():
        return None
    try:
        state = json.loads(loop_state_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    pipeline = state.get("pipeline", {})
    phase = pipeline.get("phase", "unknown")
    stage = pipeline.get("stage", "unknown")
    gates = state.get("gates_passed", {})

    return {
        "project":        project,
        "slug":           slug,
        "phase":          phase,
        "stage":          stage,
        "tier":           state.get("complexity_tier") or (
                              f"N/A ({state.get('route')})" if state.get("route") else "unknown"
                          ),
        "planning_loops": sum(1 for k in gates if k.startswith("planning/")),
        "design_loops":   sum(1 for k in gates if k.startswith("design/")),
        "next_action":    _hint_from_phase(phase, slug),
        "tdd_pairs":      tdd_breakdown_pairs(state.get("artifacts", {})),
    }


def all_features(project: str, repo_root=None) -> list:
    repo_root = Path(repo_root or REPO_ROOT)
    base = repo_root / "memory" / "features" / project
    if not base.exists():
        return []
    results = []
    for slug_dir in sorted(base.iterdir()):
        if not slug_dir.is_dir():
            continue
        status = feature_status(project, slug_dir.name, repo_root)
        if status:
            results.append(status)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pipeline state manager")
    parser.add_argument("--project",     help="Project slug")
    parser.add_argument("--slug",        help="Feature slug")
    parser.add_argument("--project-dir", dest="project_dir", help="Repo root (default: cwd)")
    parser.add_argument("--validate",    metavar="PATH", help="Validate loop_state.json at PATH")
    parser.add_argument("--status",      action="store_true", help="Print feature status JSON")
    parser.add_argument("--rebuild",     action="store_true", help="Rebuild artifacts key from filesystem")
    args = parser.parse_args()

    if args.validate:
        is_valid, error = validate_loop_state(Path(args.validate))
        if is_valid:
            print(f"Valid: {args.validate}")
        else:
            print(f"Invalid: {args.validate}\n  {error}")
            raise SystemExit(1)
        return

    if args.rebuild:
        if not args.project or not args.slug:
            print("--rebuild requires --project and --slug")
            raise SystemExit(1)
        artifacts = rebuild_artifacts(args.project, args.slug)
        state_file = REPO_ROOT / "memory" / "features" / args.project / args.slug / "loop_state.json"
        if not state_file.exists():
            print(f"No loop_state.json at {state_file}")
            raise SystemExit(1)
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["artifacts"] = artifacts
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"Rebuilt {len(artifacts)} artifact entries for {args.project}/{args.slug}")
        return

    if args.status:
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            from config_utils import ConfigResolver
            project = args.project or ConfigResolver(REPO_ROOT / "config.yml").active_project
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            raise SystemExit(1)
        print(json.dumps(all_features(project, args.project_dir or REPO_ROOT), indent=2))
        return

    if args.project and args.slug:
        phase, stage, hint = detect_phase(args.project, args.slug, args.project_dir)
        print(f"Phase: {phase}/{stage}")
        print(f"Hint:  {hint}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
