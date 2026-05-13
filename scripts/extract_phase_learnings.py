#!/usr/bin/env python
"""Extract implementation learnings from a story's failure ledger and write to agent MEMORY.md.

Called after story completes, before failure_ledger.py cleanup.
Reads failure-ledger-{STORY-KEY}.json. One entry per unique error_type.
ac_coverage_gap → qa-engineer MEMORY.md. All others → developer MEMORY.md.
Dedup is handled by update_agent_memory.py (threshold 0.60).

Usage:
  python scripts/extract_phase_learnings.py <project> <slug> <story-key> [--dry-run]

Exit codes:
  0  entries written (or dry-run with entries)
  1  no failures recorded — nothing to write
  2  error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ledger_path(project: str, slug: str, story_key: str) -> Path:
    return REPO_ROOT / "memory" / "features" / project / slug / f"failure-ledger-{story_key}.json"


def _load_records(project: str, slug: str, story_key: str) -> list[dict]:
    path = _ledger_path(project, slug, story_key)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _build_entries(records: list[dict]) -> list[tuple[str, str]]:
    """Return (agent, entry) pairs — one per unique error_type."""
    seen: set[str] = set()
    entries: list[tuple[str, str]] = []

    for r in records:
        error_type = r.get("error_type", "unknown")
        if error_type in seen:
            continue
        seen.add(error_type)

        hypothesis = r.get("hypothesis", "").strip()
        error_summary = r.get("error_summary", "").strip()
        detail = (hypothesis or error_summary)[:80]
        entry = f"Phase A {error_type} retry: {detail}" if detail else f"Phase A {error_type} retry occurred"

        agent = "qa-engineer" if error_type == "ac_coverage_gap" else "developer"
        entries.append((agent, entry))

    return entries


def _append_memory(agent: str, entry: str, dry_run: bool) -> None:
    script = REPO_ROOT / "scripts" / "update_agent_memory.py"
    if dry_run:
        print(f"  [dry-run] {agent}: {entry}")
        return
    result = subprocess.run(
        [sys.executable, str(script), agent, "append", entry],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):  # 1 = duplicate skipped
        print(f"  WARNING: update_agent_memory returned {result.returncode}: {result.stderr.strip()}")
    else:
        print(f"  learning ({agent}): {entry[:80]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("slug")
    ap.add_argument("story_key")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    records = _load_records(args.project, args.slug, args.story_key)
    if not records:
        sys.exit(1)

    entries = _build_entries(records)
    if not entries:
        sys.exit(1)

    print(f"extract_phase_learnings: {len(entries)} pattern(s) from {args.story_key} ({len(records)} failure(s))")
    for agent, entry in entries:
        _append_memory(agent, entry, args.dry_run)


if __name__ == "__main__":
    main()
