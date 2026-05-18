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
Cleanup script for failed HeadMaster runs.
Handles orphaned branches, corrupted state, stuck features.

Usage:
    python cleanup_failed_run.py -w <project> -s <feature-slug> [options]

Examples:
    python cleanup_failed_run.py -w default -s my-feature --reset-state
    python cleanup_failed_run.py -w default -s my-feature -F  # Full cleanup
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Add root scripts to path
_root = Path(__file__).parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config_utils import ConfigResolver


def find_orphaned_branches(feature_slug: str) -> list[str]:
    """Find git branches related to feature slug."""
    try:
        result = subprocess.run(
            ["git", "branch", "--list", f"*{feature_slug}*"],
            capture_output=True,
            text=True,
            check=True
        )
        branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n") if b.strip()]
        return branches
    except subprocess.CalledProcessError:
        return []


_QUIET = False  # Module-level flag set by CLI --quiet


def _log(msg: str) -> None:
    """Print only when not in quiet mode."""
    if not _QUIET:
        print(msg)


def delete_branch(branch_name: str, force: bool = False) -> bool:
    """Delete a git branch."""
    try:
        flag = "-D" if force else "-d"
        subprocess.run(
            ["git", "branch", flag, branch_name],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        _log(f"  Failed to delete branch '{branch_name}': {e.stderr.strip()}")
        return False


def reset_loop_state(memory_path: Path) -> bool:
    """Reset loop_state.json to initial state."""
    state_file = memory_path / "loop_state.json"

    if not state_file.exists():
        _log(f"  No loop_state.json at {state_file}")
        return False

    backup_file = memory_path / f"loop_state.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(state_file) as f:
            state = json.load(f)

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        _log(f"  Backup: {backup_file.name}")

        initial_state = {
            "status": "not_started",
            "phase": "planning",
            "stage": "init",
            "loop_count": 0,
            "updated_at": datetime.now().isoformat()
        }

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f, indent=2)

        _log("  Reset loop_state.json")
        return True

    except Exception as e:
        _log(f"  Failed to reset state: {e}")
        return False


def cleanup_temp_files(memory_path: Path) -> int:
    """Remove temporary files from memory directory."""
    if not memory_path.exists():
        return 0

    patterns = ["*.tmp", "*.lock", ".*.swp", "*~"]
    removed = 0

    for pattern in patterns:
        for temp_file in memory_path.rglob(pattern):
            try:
                temp_file.unlink()
                removed += 1
                _log(f"  Removed: {temp_file.name}")
            except Exception as e:
                _log(f"  Failed to remove {temp_file.name}: {e}")

    return removed


def cleanup_failed_run(
    project: str,
    feature_slug: str,
    delete_branches: bool = False,
    reset_state: bool = False
) -> bool:
    """
    Clean up after a failed feature run.

    Args:
        project: Project name
        feature_slug: Feature slug
        delete_branches: Delete orphaned git branches
        reset_state: Reset loop_state.json to initial state

    Returns:
        True if cleanup succeeded
    """
    resolver = ConfigResolver()
    memory_path = resolver.get_feature_memory_path(feature_slug, project)

    _log(f"Cleanup: {project}/{feature_slug}")

    success = True

    # 1. Clean temp files
    removed = cleanup_temp_files(memory_path)
    _log(f"  Temp files removed: {removed}")

    # 2. Reset state if requested
    if reset_state:
        if not reset_loop_state(memory_path):
            success = False

    # 3. Handle branches if requested
    if delete_branches:
        branches = find_orphaned_branches(feature_slug)
        if branches:
            for branch in branches:
                if delete_branch(branch, force=True):
                    _log(f"  Deleted branch: {branch}")
                else:
                    success = False
        else:
            _log("  No orphaned branches")

    # Final verdict — always print (even in quiet mode)
    print("OK" if success else "ERRORS")
    return success


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup failed HeadMaster runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument("-w", "--project", required=True, help="Project name")
    parser.add_argument("-s", "--slug", required=True, help="Feature slug")
    parser.add_argument("-b", "--delete-branches", action="store_true", help="Delete orphaned git branches")
    parser.add_argument("-r", "--reset-state", action="store_true", help="Reset loop_state.json to initial state")
    parser.add_argument("-F", "--full", action="store_true", help="Full cleanup (reset state + delete branches)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Minimal output: verdict only (saves tokens when called from agents)")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")

    args = parser.parse_args()

    global _QUIET
    _QUIET = args.quiet

    project = args.project
    feature_slug = args.slug

    delete_branches = args.delete_branches or args.full
    reset_state = args.reset_state or args.full

    if not delete_branches and not reset_state:
        print("No cleanup actions specified. Use -r, -b, or -F")
        parser.print_help()
        sys.exit(1)

    if args.dry_run:
        print(f"DRY RUN: {project}/{feature_slug} branches={delete_branches} state={reset_state}")
        sys.exit(0)

    success = cleanup_failed_run(project, feature_slug, delete_branches, reset_state)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
