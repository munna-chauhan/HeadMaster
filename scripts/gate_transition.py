#!/usr/bin/env python3
"""Atomic pipeline state transition. Called by skills when a gate passes.

Usage:
    python scripts/gate_transition.py <slug> <phase> <stage> [--artifact <path>]

Examples:
    python scripts/gate_transition.py my-feature planning Draft
    python scripts/gate_transition.py my-feature planning APPROVED --artifact docs/features/my-feature/planning/PRD.md
    python scripts/gate_transition.py my-feature design Architect
    python scripts/gate_transition.py my-feature design APPROVED --artifact docs/features/my-feature/design/TDD_REVIEW.md
    python scripts/gate_transition.py my-feature execute in-progress
    python scripts/gate_transition.py my-feature execute complete
"""
import json
import sys
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) < 4:
        print("Usage: gate_transition.py <slug> <phase> <stage> [--artifact <path>]", file=sys.stderr)
        sys.exit(1)

    slug = sys.argv[1]
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

    # Emit metrics event
    try:
        metrics_script = REPO_ROOT / "scripts" / "metrics.py"
        if metrics_script.exists():
            cmd = [
                sys.executable, str(metrics_script), "emit", slug, "gate_pass",
                "--phase", phase, "--stage", stage,
            ]
            subprocess.run(cmd, capture_output=True, timeout=5)
    except Exception:
        pass  # Best-effort — never block gate transition

    print(f"[gate] {slug}: {phase}/{stage}", file=sys.stderr)


if __name__ == "__main__":
    main()
