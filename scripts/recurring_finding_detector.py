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
"""Detect recurring review findings within a feature and emit developer memory entries.

Reads code-review-*.md files from docs/features/{project}/{slug}/execution/reviews/.
Extracts finding lines (any line containing a severity marker: HIGH/MEDIUM/LOW/CRITICAL).
Groups by word overlap (threshold 0.50). When a group appears in ≥2 distinct stories,
calls update_agent_memory.py to append a one-line pattern to developer MEMORY.md.

Usage:
  sh scripts/recurring_finding_detector.py <project> <slug> [--dry-run]

Exit codes:
  0  completed (entries written or nothing to write)
  2  error
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAP_THRESHOLD = 0.50
RECURRENCE_MIN = 2

STOP_WORDS = {"the", "a", "an", "is", "are", "was", "in", "of", "to", "and", "or",
              "for", "it", "with", "this", "that", "has", "have", "be", "not", "at"}

# Severity markers — part of the review output contract, not tool-specific
_SEVERITY_RE = re.compile(r'\b(CRITICAL|HIGH|MEDIUM|LOW)\b', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _story_key_from_filename(path: Path) -> str:
    """code-review-STORY-123.md → STORY-123"""
    return path.stem.replace("code-review-", "", 1)


def _extract_findings(path: Path) -> list[tuple[str, str]]:
    """Return (severity, finding_text) for each finding line in a review file."""
    findings = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _SEVERITY_RE.search(line)
        if not m:
            continue
        severity = m.group(1).upper()
        # Strip markdown noise; keep the meaningful description
        text = re.sub(r'[`*#]', '', line).strip()
        if len(text.split()) >= 4:  # skip trivially short lines
            findings.append((severity, text))
    return findings


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _word_overlap(a: str, b: str) -> float:
    wa = set(a.lower().split()) - STOP_WORDS
    wb = set(b.lower().split()) - STOP_WORDS
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _group_findings(
    per_story: dict[str, list[tuple[str, str]]]
) -> list[dict]:
    """
    Group findings across stories by word overlap.
    Returns groups where the same pattern appeared in ≥ RECURRENCE_MIN distinct stories.
    Each group: {severity, representative_text, stories: [story-key, ...]}
    """
    # Flatten: (story_key, severity, text)
    all_findings: list[tuple[str, str, str]] = []
    for story, findings in per_story.items():
        for sev, text in findings:
            all_findings.append((story, sev, text))

    groups: list[dict] = []  # {severity, text, stories: set}

    for story, sev, text in all_findings:
        matched = False
        for g in groups:
            if g["severity"] != sev:
                continue
            if _word_overlap(text, g["text"]) >= OVERLAP_THRESHOLD:
                g["stories"].add(story)
                matched = True
                break
        if not matched:
            groups.append({"severity": sev, "text": text, "stories": {story}})

    return [g for g in groups if len(g["stories"]) >= RECURRENCE_MIN]


# ---------------------------------------------------------------------------
# Memory entry generation
# ---------------------------------------------------------------------------

def _to_memory_entry(group: dict) -> str:
    stories = sorted(group["stories"])
    short = re.sub(r'\s+', ' ', group["text"])[:120]
    return f"{group['severity']} finding recurring ({len(stories)} stories): {short}"


def _append_memory(entry: str, dry_run: bool) -> None:
    script = REPO_ROOT / "scripts" / "update_agent_memory.py"
    if dry_run:
        print(f"  [dry-run] would append: {entry}")
        return
    result = subprocess.run(
        ["sh", str(script), "developer", "append", entry],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):  # 1 = duplicate skipped
        print(f"  WARNING: update_agent_memory returned {result.returncode}: {result.stderr.strip()}")
    else:
        print(f"  memory: {entry[:80]}...")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    reviews_dir = REPO_ROOT / "docs" / "features" / args.project / args.slug / "execution" / "reviews"
    if not reviews_dir.is_dir():
        # No reviews yet — nothing to do
        sys.exit(0)

    review_files = sorted(reviews_dir.glob("code-review-*.md"))
    if len(review_files) < RECURRENCE_MIN:
        sys.exit(0)

    per_story: dict[str, list[tuple[str, str]]] = {}
    for path in review_files:
        key = _story_key_from_filename(path)
        findings = _extract_findings(path)
        if findings:
            per_story[key] = findings

    recurring = _group_findings(per_story)
    if not recurring:
        sys.exit(0)

    print(f"recurring_finding_detector: {len(recurring)} recurring pattern(s) in {args.project}/{args.slug}")
    for group in recurring:
        entry = _to_memory_entry(group)
        _append_memory(entry, args.dry_run)


if __name__ == "__main__":
    main()
