#!/usr/bin/env python3
"""SessionStart hook — prints project status and active feature phases."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = REPO_ROOT / "docs" / "features"

# Phase detection: ordered list of (artifact glob, folder_key, phase, hint)
# folder_key: "planning" | "design" | "breakdown"
PHASE_CHECKS = [
    ("JIRA_BREAKDOWN.md", "breakdown", "breakdown", "Run /execute {slug}"),
    ("TDD_REVIEW.md", "design", "design/Review", "Run /design {slug}"),
    ("TDD*.md", "design", "design/Engineer", "Run /design {slug}"),
    ("SYSTEM_DESIGN_NOTES.md", "design", "design/Architect", "Run /design {slug}"),
    ("PRD.md", "planning", "planning/Draft", "Run /plan {slug}"),
    ("DISCOVERY_NOTES.md", "planning", "planning/Discover", "Run /plan {slug}"),
    ("FEATURE_DRAFT.md", "planning", "planning/Discover", "Run /plan {slug}"),
]


def read_project_key() -> str:
    """Extract project_key from config.yml (simple parser, no pyyaml)."""
    cfg = REPO_ROOT / "config.yml"
    if not cfg.exists():
        return ""
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if line.startswith("project_key:"):
            val = line.split(":", 1)[1].split("#")[0].strip().strip('"').strip("'")
            return val
    return ""


def _breakdown_phase(breakdown: Path, slug: str) -> tuple[str, str]:
    """Distinguish between breakdown-ready, execute-in-progress, and execute-complete."""
    bd_file = breakdown / "JIRA_BREAKDOWN.md"
    if not bd_file.exists():
        return "planning/Init", f"Run /plan {slug}"
    try:
        content = bd_file.read_text(encoding="utf-8")
    except Exception:
        return "execute/ready", f"Run /execute {slug}"

    in_progress_markers = ["🔄 IN PROGRESS", "🔍 SCANNING", "👁️ IN REVIEW", "🧪 IN QA"]
    if any(m in content for m in in_progress_markers):
        return "execute/in-progress", f"Run /execute {slug} (resume)"

    # Check if all stories are complete
    has_new = "⏳ NEW" in content
    has_complete = "✅ COMPLETE" in content
    if has_complete and not has_new:
        return "execute/complete", f"Run /breakdown {slug} merge-gate"

    # Breakdown exists but execution not started
    return "execute/ready", f"Run /execute {slug}"


def detect_phase(planning: Path, design: Path, breakdown: Path) -> tuple[str, str]:
    """Return (phase, next_action_hint) by finding the highest completed artifact."""
    slug = planning.parent.name

    # Check breakdown first (most complete)
    if breakdown.is_dir() and (breakdown / "JIRA_BREAKDOWN.md").exists():
        return _breakdown_phase(breakdown, slug)

    # Walk design and planning checks
    for artifact, folder_key, phase, hint in PHASE_CHECKS:
        if folder_key == "breakdown":
            continue  # handled above
        folder = design if folder_key == "design" else planning
        if list(folder.glob(artifact)):
            return phase, hint.format(slug=slug)

    return "planning/Init", f"Run /plan {slug}"


def read_model_from_event() -> str:
    """Read model from SessionStart hook event payload (stdin JSON)."""
    import sys, json
    try:
        if not sys.stdin.isatty():
            payload = json.load(sys.stdin)
            return payload.get("model", "")
    except (json.JSONDecodeError, Exception):
        pass
    return ""


def main() -> None:
    project_key = read_project_key() or "(not set)"
    model = read_model_from_event()
    model_display = f" | model: {model}" if model else ""
    print(f"[HeadMaster] Project: {project_key}{model_display}")

    # Persist project key as env var for skills to use
    import os
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file and project_key and project_key != "(not set)":
        with open(env_file, "a", encoding="utf-8") as f:
            f.write(f'export HEAD_MASTER_PROJECT_KEY="{project_key}"\n')

    if not FEATURES_DIR.is_dir():
        print("[HeadMaster] No active features. Run /navigate to start.")
        return

    active = []
    for feat in sorted(FEATURES_DIR.iterdir()):
        if not feat.is_dir():
            continue
        planning = feat / "planning"
        if not planning.is_dir():
            continue
        design = feat / "design"
        breakdown = feat / "breakdown"
        phase, hint = detect_phase(planning, design, breakdown)
        active.append((feat.name, phase, hint))

    if not active:
        print("[HeadMaster] No active features. Run /navigate to start.")
        return

    print("Active features:")
    for slug, phase, hint in active:
        print(f"  {slug}: {phase} — {hint}")


if __name__ == "__main__":
    main()
