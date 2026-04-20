#!/usr/bin/env python3
"""Deterministic stop check for /design skill. Replaces haiku agent."""
import json
import sys
from pathlib import Path

def main():
    args = sys.argv[1] if len(sys.argv) > 1 else ""
    slug = args.strip()
    if not slug:
        features = Path("docs/features")
        if features.exists():
            dirs = [d.name for d in features.iterdir() if d.is_dir()]
            slug = dirs[0] if len(dirs) == 1 else ""

    if not slug:
        print(json.dumps({"ok": False, "reason": "Cannot determine feature slug"}))
        sys.exit(0)

    # Check lite tier: IMPLEMENTATION_BRIEF.md
    brief = Path(f"docs/features/{slug}/design/IMPLEMENTATION_BRIEF.md")
    if brief.exists():
        content = brief.read_text(encoding="utf-8", errors="ignore")
        # Count sections (## headings)
        sections = [l for l in content.split("\n") if l.strip().startswith("## ")]
        if len(sections) >= 5:
            print(json.dumps({"ok": True}))
            sys.exit(0)

    # Check standard/full tier: TDD_REVIEW.md with APPROVED or CONDITIONAL
    review = Path(f"docs/features/{slug}/design/TDD_REVIEW.md")
    if review.exists():
        head = review.read_bytes()[:500].decode("utf-8", errors="ignore")
        if "APPROVED" in head or "CONDITIONAL" in head:
            print(json.dumps({"ok": True}))
            sys.exit(0)

    # Check if waiting for user input
    try:
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        last_msg = payload.get("last_assistant_message", "")
        if "AskUserQuestion" in last_msg or "max_loops exceeded" in last_msg or "escalating to human" in last_msg:
            print(json.dumps({"ok": True}))
            sys.exit(0)
    except Exception:
        pass

    print(json.dumps({"ok": False, "reason": "Design not finalized"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
