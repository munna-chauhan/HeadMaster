#!/usr/bin/env python3
"""Auto-braindump at orange threshold — progressive context saving.

Triggered by token_budget.py when session age reaches orange threshold.
Writes compressed progress state without terminating execution.

Called via: python .claude/hooks/auto_braindump.py <slug> <turn_count>
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main():
    if len(sys.argv) < 3:
        sys.exit(0)

    slug = sys.argv[1]
    turn_count = int(sys.argv[2])

    memory_dir = REPO_ROOT / "memory" / "features" / slug
    if not memory_dir.exists():
        sys.exit(0)  # No active feature

    # Find most recent session handoff
    existing = sorted(memory_dir.glob("session-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    last_content = ""
    if existing:
        try:
            last_content = existing[0].read_text(encoding="utf-8")
        except Exception:
            pass

    # Write incremental braindump
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    braindump_path = memory_dir / f"session-{ts}-auto-braindump.md"

    content = f"""# Auto-Braindump: {slug}

**Timestamp:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC
**Reason:** Session age reached orange threshold ({turn_count} turns)
**Status:** Execution continuing (not terminated)

## Context Checkpoint

This is an automatic checkpoint. Execution continues.
If session terminates unexpectedly, resume from last completed story.

## Last Known State

{last_content if last_content else "No prior handoff found. Check JIRA_BREAKDOWN.md for current story status."}

## Resume Command

```bash
cd {REPO_ROOT.name}
/navigate {slug}  # Auto-detect phase and resume
```
"""

    braindump_path.write_text(content, encoding="utf-8")
    print(f"[auto-braindump] Checkpoint saved: {braindump_path.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
