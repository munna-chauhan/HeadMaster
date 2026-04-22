#!/usr/bin/env python3
"""
Enhanced metrics collection with structured data - Phase 2.
Writes to feature-specific files, but still read-only (no analysis yet).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

def get_active_feature():
    """Get currently active feature slug."""
    flag_file = Path.home() / ".claude" / ".HeadMaster-active"
    if flag_file.exists():
        try:
            flag = json.loads(flag_file.read_text())
            return flag.get("slug")
        except Exception:
            pass
    return None

def append_tool_call(slug: str, tool_name: str, duration_ms: int = 0):
    """Append tool call to feature metrics."""
    if not slug:
        return

    try:
        metrics_file = REPO_ROOT / "memory" / "features" / slug / "skill_metrics.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Read existing
        if metrics_file.exists():
            data = json.loads(metrics_file.read_text())
        else:
            data = {
                "feature": slug,
                "started": datetime.now(timezone.utc).isoformat(),
                "tool_calls": []
            }

        # Append new call
        data["tool_calls"].append({
            "tool": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms
        })

        # Write atomically
        tmp = metrics_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(metrics_file)

    except Exception as e:
        # Log error but never block
        error_log = REPO_ROOT / "memory" / "monitoring-logs" / "errors.log"
        try:
            with open(error_log, "a") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()} skill_metrics error: {e}\n")
        except Exception:
            pass

def main():
    """Hook entry point."""
    try:
        # Get tool name from stdin payload
        if not sys.stdin.isatty():
            payload = json.loads(sys.stdin.read())
            tool_name = payload.get("tool_name", "unknown")

            # Try to extract duration if available
            duration_ms = payload.get("duration_ms", 0)
            if duration_ms == 0 and "tool_input" in payload:
                # Some hooks provide timing data in tool_input
                tool_input = payload.get("tool_input", {})
                duration_ms = tool_input.get("duration_ms", 0)
        else:
            # Test mode
            tool_name = sys.argv[1] if len(sys.argv) > 1 else "test"
            duration_ms = 0

        slug = get_active_feature()
        if slug:
            append_tool_call(slug, tool_name, duration_ms)

    except Exception:
        pass  # Silent failure

if __name__ == "__main__":
    main()
