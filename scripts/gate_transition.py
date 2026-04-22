#!/usr/bin/env python3
"""Atomic pipeline state transition. Called by skills when a gate passes.

Usage:
    python scripts/gate_transition.py <slug> <phase> <stage> [--artifact <path>]
    python scripts/gate_transition.py <slug> rollback

Examples:
    python scripts/gate_transition.py my-feature planning Draft
    python scripts/gate_transition.py my-feature planning APPROVED --artifact docs/features/my-feature/planning/PRD.md
    python scripts/gate_transition.py my-feature design Architect
    python scripts/gate_transition.py my-feature design APPROVED --artifact docs/features/my-feature/design/TDD_REVIEW.md
    python scripts/gate_transition.py my-feature execute in-progress
    python scripts/gate_transition.py my-feature execute complete
    python scripts/gate_transition.py my-feature rollback  # restore previous state from backup
"""
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) < 3:
        print("Usage: gate_transition.py <slug> <phase> <stage> [--artifact <path>] | <slug> rollback", file=sys.stderr)
        sys.exit(1)

    slug = sys.argv[1]

    # Handle rollback command
    if len(sys.argv) == 3 and sys.argv[2] == "rollback":
        memory_dir = REPO_ROOT / "memory" / "features" / slug
        state_file = memory_dir / "loop_state.json"
        backup_file = memory_dir / "loop_state.json.bak"

        if not backup_file.exists():
            print(f"[gate] No backup found for {slug}", file=sys.stderr)
            sys.exit(1)

        # Restore backup
        backup_file.replace(state_file)
        print(f"[gate] {slug}: restored from backup", file=sys.stderr)
        sys.exit(0)

    if len(sys.argv) < 4:
        print("Usage: gate_transition.py <slug> <phase> <stage> [--artifact <path>] | <slug> rollback", file=sys.stderr)
        sys.exit(1)

    phase = sys.argv[2]
    stage = sys.argv[3]

    artifact = None
    if "--artifact" in sys.argv:
        idx = sys.argv.index("--artifact")
        if idx + 1 < len(sys.argv):
            artifact = sys.argv[idx + 1]

    memory_dir = REPO_ROOT / "memory" / "features" / slug
    memory_dir.mkdir(parents=True, exist_ok=True)
    state_file = memory_dir / "loop_state.json"

    # Read existing state
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {}

    # Backup current state before updating
    if state_file.exists():
        backup_file = state_file.with_suffix(".json.bak")
        state_file_content = state_file.read_text(encoding="utf-8")
        backup_file.write_text(state_file_content, encoding="utf-8")

    # Update pipeline key atomically
    state["pipeline"] = {
        "phase": phase,
        "stage": stage,
        "gate_passed": datetime.now(timezone.utc).isoformat(),
    }
    if artifact:
        state["pipeline"]["artifact"] = artifact

    # Write atomically (write to temp, then rename)
    tmp_file = state_file.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp_file.replace(state_file)

    print(f"[gate] {slug}: {phase}/{stage}", file=sys.stderr)

    # Phase 3: Trigger gate analysis hook
    try:
        hook_script = REPO_ROOT / ".claude" / "hooks" / "gate_passed.py"
        if hook_script.exists():
            import subprocess
            subprocess.run(
                ["python", str(hook_script), slug, phase, stage],
                timeout=10,
                capture_output=True
            )
    except Exception:
        pass  # Silent failure - never block gate transition


if __name__ == "__main__":
    main()
