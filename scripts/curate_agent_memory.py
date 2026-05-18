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
"""Deduplicate and age-out entries in agent MEMORY.md files.

Usage:
  sh scripts/curate_agent_memory.py <agent> [--age-days N] [--dry-run]
  sh scripts/curate_agent_memory.py --all [--age-days N] [--dry-run]

Exit codes:
  0  changes written
  1  no changes needed
  2  error
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAP_THRESHOLD = 0.40
DEFAULT_AGE_DAYS = 90

STOP_WORDS = {"the", "a", "an", "is", "are", "was", "in", "of", "to", "and", "or", "for", "it", "with"}


def _word_overlap(a: str, b: str) -> float:
    wa = set(a.lower().split()) - STOP_WORDS
    wb = set(b.lower().split()) - STOP_WORDS
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _entry_date(line: str) -> date | None:
    """Extract date from '- [YYYY-MM-DD] ...' format."""
    stripped = line.lstrip("- ").strip()
    if stripped.startswith("[") and "] " in stripped:
        date_str = stripped[1:stripped.index("]")]
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass
    return None


def _entry_text(line: str) -> str:
    """Strip bullet and date prefix."""
    text = line.lstrip("- ").strip()
    if text.startswith("[") and "] " in text:
        return text.split("] ", 1)[1]
    return text


def _curate(path: Path, age_days: int, dry_run: bool) -> dict:
    lines_in = path.read_text(encoding="utf-8").splitlines()

    cutoff = date.today() - timedelta(days=age_days)
    aged_out = 0
    active: list[str] = []

    for line in lines_in:
        if not line.strip() or not line.strip().startswith("-"):
            active.append(line)
            continue
        d = _entry_date(line)
        if d and d < cutoff:
            aged_out += 1
        else:
            active.append(line)

    # Deduplicate: keep the most recent phrasing for each cluster
    entry_lines = [l for l in active if l.strip().startswith("-")]
    non_entry_lines = [l for l in active if not l.strip().startswith("-")]

    kept: list[str] = []
    merged = 0

    for line in entry_lines:
        text = _entry_text(line)
        duplicate_of = None
        for i, existing in enumerate(kept):
            if _word_overlap(text, _entry_text(existing)) >= OVERLAP_THRESHOLD:
                duplicate_of = i
                break
        if duplicate_of is not None:
            # Keep the more recent one (later date wins)
            existing_date = _entry_date(kept[duplicate_of])
            this_date = _entry_date(line)
            if this_date and existing_date and this_date > existing_date:
                kept[duplicate_of] = line
            merged += 1
        else:
            kept.append(line)

    result_lines = non_entry_lines + kept
    lines_out = len(result_lines)

    changed = (aged_out > 0 or merged > 0)

    if changed and not dry_run:
        path.with_suffix(".md.bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text("\n".join(result_lines) + "\n", encoding="utf-8")

    return {
        "lines_in": len(lines_in),
        "lines_out": lines_out,
        "merged": merged,
        "aged_out": aged_out,
        "changed": changed,
    }


def _memory_paths(agent: str | None) -> list[Path]:
    if agent:
        return [REPO_ROOT / "memory" / "agents" / agent / "MEMORY.md"]
    return sorted((REPO_ROOT / "memory" / "agents").glob("*/MEMORY.md"))


def main() -> None:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("agent", nargs="?")
    group.add_argument("--all", action="store_true")
    ap.add_argument("--age-days", type=int, default=DEFAULT_AGE_DAYS)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paths = _memory_paths(None if args.all else args.agent)
    if not paths:
        print("No MEMORY.md files found.", file=sys.stderr)
        sys.exit(2)

    any_changed = False
    errors = False

    for path in paths:
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            errors = True
            continue
        try:
            r = _curate(path, args.age_days, args.dry_run)
            tag = "[dry-run] " if args.dry_run else ""
            agent_name = path.parent.name
            print(
                f"{tag}{agent_name}: {r['lines_in']}→{r['lines_out']} lines "
                f"(merged={r['merged']}, aged_out={r['aged_out']})"
            )
            if r["changed"]:
                any_changed = True
        except Exception as exc:
            print(f"ERROR curating {path}: {exc}", file=sys.stderr)
            errors = True

    if errors:
        sys.exit(2)
    sys.exit(0 if any_changed else 1)


if __name__ == "__main__":
    main()
