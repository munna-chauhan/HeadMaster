#!/usr/bin/env python
"""SessionStart hook — setup projects, print status, validate state."""
import os
import subprocess
import sys
from pathlib import Path

# Set UTF-8 encoding for stdout on Windows to handle emoji
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = REPO_ROOT / "docs" / "features"

# Add scripts directory to path for imports
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from state_manager import detect_phase as detect_phase_shared
from state_manager import validate_loop_state, format_validation_error
from config_utils import ConfigResolver


def read_project_key() -> str:
    """Extract project_key for the active project via ConfigResolver."""
    try:
        resolver = ConfigResolver(REPO_ROOT / "config.yml")
        return resolver.get("project_key", "") or ""
    except Exception:
        return ""


def read_active_project() -> str:
    """Extract active project from config.yml via ConfigResolver."""
    try:
        resolver = ConfigResolver(REPO_ROOT / "config.yml")
        return resolver.active_project
    except Exception:
        return "default"


def read_model_from_event() -> str:
    """Read model from SessionStart hook event payload (stdin JSON)."""
    import sys, json
    try:
        # Only read stdin if it's a pipe (hook context), never block on terminal
        if not sys.stdin.isatty():
            raw = sys.stdin.read(1024)  # cap read — we only need the model field
            if raw.strip():
                payload = json.loads(raw)
                return payload.get("model", "")
    except Exception:
        pass
    return ""


def main() -> None:
    # Self-heal .remember/logs/ so hook-errors.log is always writable (INFRA-01)
    logs_dir = REPO_ROOT / ".remember" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "hook-errors.log").touch(exist_ok=True)

    # Setup project directories (absorbed from session_reset.py)
    setup_script = REPO_ROOT / "scripts" / "setup_projects.py"
    if setup_script.exists():
        try:
            subprocess.run(["python", str(setup_script)], cwd=str(REPO_ROOT),
                           capture_output=True, timeout=5, check=False)
        except Exception:
            pass

    project_key = read_project_key() or "(not set)"
    project = read_active_project()
    model = read_model_from_event()
    model_display = f" | model: {model}" if model else ""
    print(f"[HeadMaster] Project: {project_key}{model_display}")

    # Persist project key as env var for skills to use
    import os
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file and project_key and project_key != "(not set)":
        with open(env_file, "a", encoding="utf-8") as f:
            f.write(f'export HEAD_MASTER_PROJECT_KEY="{project_key}"\n')

    project_dir = FEATURES_DIR / project
    if not project_dir.is_dir():
        print("[HeadMaster] No features. /init-feature to start.")
        return

    MAX_DISPLAY = 5  # Cap output to prevent context bloat

    active = []
    corrupted = []
    for feat in sorted(project_dir.iterdir()):
        if not feat.is_dir():
            continue
        slug = feat.name

        # Validate loop_state.json before phase detection
        loop_state_path = REPO_ROOT / "memory" / "features" / project / slug / "loop_state.json"
        is_valid, error_msg = validate_loop_state(loop_state_path)
        if not is_valid:
            corrupted.append((slug, error_msg))
            continue

        try:
            phase, stage, hint = detect_phase_shared(project, slug, str(REPO_ROOT))
            # Skip completed features — no need to display
            if stage == "complete":
                continue
            active.append((slug, f"{phase}/{stage}", hint))
        except Exception:
            continue

    # Show corrupted features (max 2 to limit output)
    for slug, error_msg in corrupted[:2]:
        print(format_validation_error(project, slug, error_msg))
    if len(corrupted) > 2:
        print(f"  +{len(corrupted) - 2} more corrupted features")

    # Warn if repo registry is missing for active project
    registry = REPO_ROOT / "memory" / "projects" / project / "repo-registry.yml"
    if not registry.exists():
        print(f"[HeadMaster] Repo registry not found. Run /setup-env to cache repo/module/tech data.")

    if not active and not corrupted:
        print("[HeadMaster] No features. /init-feature to start.")
        return

    if active:
        shown = active[:MAX_DISPLAY]
        for slug, phase, hint in shown:
            print(f"  {slug}: {phase}")
        if len(active) > MAX_DISPLAY:
            print(f"  +{len(active) - MAX_DISPLAY} more features")


if __name__ == "__main__":
    main()
