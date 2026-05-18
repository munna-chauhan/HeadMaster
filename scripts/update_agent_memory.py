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
"""Atomic patch for agent MEMORY.md files. Called by /retrospect after human approval.

Usage:
    sh scripts/update_agent_memory.py <agent> append "<entry>"
    sh scripts/update_agent_memory.py <agent> show
    sh scripts/update_agent_memory.py <agent> validate

Writes backup as MEMORY.md.bak before any change.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_CAP = 200  # lines


def _memory_path(agent: str) -> Path:
    return REPO_ROOT / "memory" / "agents" / agent / "MEMORY.md"


def _backup(path: Path) -> None:
    if path.exists():
        path.with_suffix(".md.bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


STOP_WORDS = {"the", "a", "an", "is", "are", "was", "in", "of", "to", "and", "or", "for", "it", "with"}
DEDUP_THRESHOLD = 0.60


def _word_overlap(a: str, b: str) -> float:
    """Overlap ratio relative to the shorter string, stop-words excluded.

    Uses min(len_a, len_b) as denominator so paraphrased entries with different
    lengths are still caught (e.g. "add async AC section" vs "async AC section
    needed when feature involves event-driven flows").
    """
    wa = set(a.lower().split()) - STOP_WORDS
    wb = set(b.lower().split()) - STOP_WORDS
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _find_duplicate(entry: str, lines: list[str]) -> str | None:
    """Return the first existing line that is too similar to entry, or None."""
    for line in lines:
        # Strip bullet/date prefix: "- [2026-05-05] actual content"
        text = line.lstrip("- ").strip()
        if text.startswith("[") and "] " in text:
            text = text.split("] ", 1)[1]
        if _word_overlap(entry, text) >= DEDUP_THRESHOLD:
            return line.strip()
    return None


def cmd_append(agent: str, entry: str) -> None:
    path = _memory_path(agent)
    if not path.exists():
        print(f"[memory] No MEMORY.md for agent '{agent}': {path}", file=sys.stderr)
        sys.exit(1)

    _backup(path)
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    if len(lines) >= MEMORY_CAP:
        print(f"[memory] {agent}/MEMORY.md is at cap ({MEMORY_CAP} lines). Run /curate-memory {agent} first.", file=sys.stderr)
        sys.exit(1)

    duplicate = _find_duplicate(entry.strip(), lines)
    if duplicate:
        print(f"[memory] SKIPPED — too similar to existing entry:\n  existing: {duplicate}\n  new:      {entry.strip()}", file=sys.stderr)
        sys.exit(0)

    ts = datetime.now(timezone.utc).date().isoformat()
    new_entry = f"- [{ts}] {entry.strip()}"
    path.write_text(content.rstrip() + "\n" + new_entry + "\n", encoding="utf-8")
    print(f"[memory] Appended to {agent}/MEMORY.md", file=sys.stderr)


def cmd_show(agent: str) -> None:
    path = _memory_path(agent)
    if not path.exists():
        print(f"[memory] No MEMORY.md for agent '{agent}'")
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    print(f"{agent}/MEMORY.md — {len(lines)} / {MEMORY_CAP} lines")
    print(path.read_text(encoding="utf-8"))


def cmd_validate(agent: str) -> None:
    path = _memory_path(agent)
    if not path.exists():
        print(f"MISSING: {path}", file=sys.stderr)
        sys.exit(1)
    lines = path.read_text(encoding="utf-8").splitlines()
    pct = len(lines) / MEMORY_CAP * 100
    status = "OK" if len(lines) < MEMORY_CAP else "AT_CAP"
    print(f"{status}: {agent}/MEMORY.md — {len(lines)}/{MEMORY_CAP} lines ({pct:.0f}%)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    agent, cmd = sys.argv[1], sys.argv[2]

    if cmd == "append":
        if len(sys.argv) < 4:
            print("Usage: update_agent_memory.py <agent> append <entry>", file=sys.stderr)
            sys.exit(1)
        cmd_append(agent, " ".join(sys.argv[3:]))
    elif cmd == "show":
        cmd_show(agent)
    elif cmd == "validate":
        cmd_validate(agent)
    else:
        print(f"Unknown command: {cmd}. Valid: append | show | validate", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
