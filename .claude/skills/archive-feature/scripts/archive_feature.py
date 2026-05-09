#!/usr/bin/env python
"""
Archive completed features to clean up project.
Moves docs and memory to archive directories.

Usage:
    python archive_feature.py archive -w <project> -s <feature-slug> [-f]
    python archive_feature.py list -w <project>
    python archive_feature.py restore -w <project> -s <feature-slug>
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

# Find HeadMaster root (walk up to config.yml) and add scripts to path
def _find_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "config.yml").exists():
            return p
        p = p.parent
    raise FileNotFoundError("config.yml not found in any parent directory")

_root_scripts = _find_root() / "scripts"
if str(_root_scripts) not in sys.path:
    sys.path.insert(0, str(_root_scripts))

from config_utils import ConfigResolver


def is_feature_completed(memory_path: Path) -> bool:
    """Check if feature is completed."""
    state_file = memory_path / "loop_state.json"
    if not state_file.exists():
        return False

    with open(state_file, encoding="utf-8") as f:
        state = json.load(f)
        return state.get("status") == "completed"


def archive_feature(project: str, feature_slug: str, force: bool = False) -> bool:
    """Archive a feature."""
    resolver = ConfigResolver()
    feature_path = resolver.get_features_path(project) / feature_slug
    memory_path = resolver.get_feature_memory_path(feature_slug, project)

    # Check if exists
    if not feature_path.exists() and not memory_path.exists():
        print(f"❌ Feature not found: {feature_slug}")
        return False

    # Check completion status
    if not force and not is_feature_completed(memory_path):
        print(f"⚠️  Feature '{feature_slug}' not completed. Use --force to archive anyway.")
        return False

    # Create archive directories
    archive_docs_path = resolver.get_features_path(project).parent / "archive" / feature_slug
    archive_memory_path = resolver.hm_root / "memory" / "features" / project / "archive" / feature_slug

    archive_docs_path.parent.mkdir(parents=True, exist_ok=True)
    archive_memory_path.parent.mkdir(parents=True, exist_ok=True)

    # Move docs
    if feature_path.exists():
        print(f"📦 Moving docs: {feature_path} → {archive_docs_path}")
        shutil.move(str(feature_path), str(archive_docs_path))

    # Move memory
    if memory_path.exists():
        print(f"📦 Moving memory: {memory_path} → {archive_memory_path}")
        shutil.move(str(memory_path), str(archive_memory_path))

    # Create archive metadata
    metadata = {
        "slug": feature_slug,
        "archived_at": datetime.now().isoformat(),
        "project": project
    }

    metadata_file = archive_memory_path / "archive_metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Feature '{feature_slug}' archived successfully")
    return True


def list_archived_features(project: str):
    """List archived features."""
    resolver = ConfigResolver()
    archive_path = resolver.hm_root / "memory" / "features" / project / "archive"

    if not archive_path.exists():
        print(f"No archived features in project '{project}'")
        return

    print(f"\n📦 Archived Features: {project}")
    print("=" * 60)

    for feature_dir in archive_path.iterdir():
        if not feature_dir.is_dir():
            continue

        metadata_file = feature_dir / "archive_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, encoding="utf-8") as f:
                metadata = json.load(f)
                archived_at = metadata.get("archived_at", "unknown")
                print(f"  - {feature_dir.name} (archived: {archived_at})")
        else:
            print(f"  - {feature_dir.name}")


def restore_feature(project: str, feature_slug: str) -> bool:
    """Restore archived feature."""
    resolver = ConfigResolver()
    archive_docs_path = resolver.get_features_path(project).parent / "archive" / feature_slug
    archive_memory_path = resolver.hm_root / "memory" / "features" / project / "archive" / feature_slug

    if not archive_docs_path.exists() and not archive_memory_path.exists():
        print(f"❌ Archived feature not found: {feature_slug}")
        return False

    feature_path = resolver.get_features_path(project) / feature_slug
    memory_path = resolver.get_feature_memory_path(feature_slug, project)

    # Restore docs
    if archive_docs_path.exists():
        print(f"📂 Restoring docs: {archive_docs_path} → {feature_path}")
        shutil.move(str(archive_docs_path), str(feature_path))

    # Restore memory
    if archive_memory_path.exists():
        print(f"📂 Restoring memory: {archive_memory_path} → {memory_path}")
        shutil.move(str(archive_memory_path), str(memory_path))

    print(f"✅ Feature '{feature_slug}' restored successfully")
    return True


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Archive, list, or restore completed features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # archive subcommand
    archive_parser = subparsers.add_parser("archive", help="Archive a completed feature")
    archive_parser.add_argument("-w", "--project", required=True, help="Project name")
    archive_parser.add_argument("-s", "--slug", required=True, help="Feature slug")
    archive_parser.add_argument("-f", "--force", action="store_true", help="Force archive even if not completed")
    archive_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    archive_parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")

    # list subcommand
    list_parser = subparsers.add_parser("list", help="List archived features")
    list_parser.add_argument("-w", "--project", required=True, help="Project name")
    list_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # restore subcommand
    restore_parser = subparsers.add_parser("restore", help="Restore an archived feature")
    restore_parser.add_argument("-w", "--project", required=True, help="Project name")
    restore_parser.add_argument("-s", "--slug", required=True, help="Feature slug")
    restore_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    restore_parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")

    args = parser.parse_args()

    if args.command == "archive":
        if args.dry_run:
            print(f"[DRY RUN] Would archive {args.project}/{args.slug} (force={args.force})")
            sys.exit(0)
        success = archive_feature(args.project, args.slug, args.force)
        sys.exit(0 if success else 1)

    elif args.command == "list":
        list_archived_features(args.project)
        sys.exit(0)

    elif args.command == "restore":
        if args.dry_run:
            print(f"[DRY RUN] Would restore {args.project}/{args.slug}")
            sys.exit(0)
        success = restore_feature(args.project, args.slug)
        sys.exit(0 if success else 2)


if __name__ == "__main__":
    main()
