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
Run logger for HeadMaster observability.
Appends timestamped decision entries to run-log.md for post-failure debugging.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone


def log_decision(project: str, slug: str, phase: str, decision: str, input_summary: str, confidence: str = None) -> None:
    """
    Append decision entry to run-log.md.

    Args:
        project: Project slug (e.g., "acme")
        slug: Feature slug (e.g., "user-auth")
        phase: Pipeline phase (e.g., "Planning/Discover", "Execute/Phase A")
        decision: Decision made (e.g., "ESCALATE", "AUTO_RESOLVE", "RETRY")
        input_summary: Brief summary of input that drove decision (max 200 chars)
        confidence: Optional confidence level (e.g., "HIGH", "MEDIUM", "LOW")
    """
    # Construct path: memory/features/{project}/{slug}/run-log.md
    hm_root = Path(__file__).parent.parent
    log_path = hm_root / "memory" / "features" / project / slug / "run-log.md"

    # Create parent directories if missing
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Format timestamp (ISO 8601)
    timestamp = datetime.now(timezone.utc).isoformat()

    # Format entry
    conf_str = f" confidence={confidence}" if confidence else ""
    entry = f"[{timestamp}] [{phase}] [{decision}] input=\"{input_summary}\"{conf_str}\n"

    # Append to log (create if missing)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)

    # Size check — warn if exceeds 500KB (append-only, no auto-truncation)
    size_kb = log_path.stat().st_size / 1024
    if size_kb > 500:
        print(f"WARNING: run-log.md exceeds 500KB ({size_kb:.1f}KB) — consider archiving old entries", file=sys.stderr)


if __name__ == "__main__":
    # CLI usage: python run_logger.py <project> <slug> <phase> <decision> <input_summary> [confidence]
    if len(sys.argv) < 6:
        print("Usage: run_logger.py <project> <slug> <phase> <decision> <input_summary> [confidence]", file=sys.stderr)
        sys.exit(1)

    project = sys.argv[1]
    slug = sys.argv[2]
    phase = sys.argv[3]
    decision = sys.argv[4]
    input_summary = sys.argv[5]
    confidence = sys.argv[6] if len(sys.argv) > 6 else None

    log_decision(project, slug, phase, decision, input_summary, confidence)
    print(f"Decision logged to memory/features/{project}/{slug}/run-log.md", file=sys.stderr)
