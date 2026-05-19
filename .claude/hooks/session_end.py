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
"""SessionEnd hook — auto-save minimal state to prevent lost context on crash/timeout.

Writes a lightweight session snapshot to memory/features/{project}/{slug}/.
Not a full /handoff — just enough to resume: phase, branch, last action.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def main():
    try:
        from config_utils import ConfigResolver
        resolver = ConfigResolver(REPO_ROOT / "config.yml")
        project = resolver.active_project
    except Exception:
        sys.exit(0)

    # Find active feature
    memory_base = REPO_ROOT / "memory" / "features" / project
    if not memory_base.exists():
        sys.exit(0)

    active_slug = None
    for slug_dir in memory_base.iterdir():
        if slug_dir.is_dir() and (slug_dir / "loop_state.json").exists():
            active_slug = slug_dir.name
            break  # take most recent

    if not active_slug:
        sys.exit(0)

    # Get current branch
    try:
        r = subprocess.run(["git", "branch", "--show-current"],
                           capture_output=True, text=True, timeout=5, cwd=str(REPO_ROOT))
        branch = r.stdout.strip() or "unknown"
    except Exception:
        branch = "unknown"

    # Write auto-snapshot (not a full handoff — just recovery state)
    snapshot = {
        "auto_saved": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "slug": active_slug,
        "branch": branch,
    }

    snapshot_path = memory_base / active_slug / "auto-snapshot.json"
    try:
        snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Background memory consolidation — compress agent memory files without blocking session end.
    # Popen (fire-and-forget): session exits immediately, consolidation runs in background.
    try:
        compress_script = REPO_ROOT / "scripts" / "compress.py"
        if compress_script.exists():
            subprocess.Popen(
                ["sh", str(compress_script), "--consolidate-memory"],
                cwd=str(REPO_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
