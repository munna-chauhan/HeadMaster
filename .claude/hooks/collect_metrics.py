#!/usr/bin/env python3
"""
Passive metrics collection hook - Phase 1.
OBSERVE ONLY - writes to separate log, doesn't modify anything.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = REPO_ROOT / "memory" / "monitoring-logs" / "metrics_collection.log"

def log_metric(event_type: str, data: dict):
    """Append metric to observation log (Phase 1: observe only)."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "data": data
        }

        # Append to log file
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")

    except Exception as e:
        # Silent failure - never block execution
        error_log = REPO_ROOT / "memory" / "monitoring-logs" / "errors.log"
        try:
            with open(error_log, "a") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()} collect_metrics error: {e}\n")
        except Exception:
            pass  # Even error logging fails silently

def main():
    """Main entry point for hook."""
    try:
        # Read stdin for hook payload
        if not sys.stdin.isatty():
            payload = json.loads(sys.stdin.read())
        else:
            payload = {}

        # Extract relevant data
        event_type = payload.get("hookEventName", "unknown")

        # Check for active feature
        flag_file = Path.home() / ".claude" / ".HeadMaster-active"
        slug = None
        if flag_file.exists():
            try:
                flag = json.loads(flag_file.read_text())
                slug = flag.get("slug")
            except Exception:
                pass

        # Log the observation
        log_metric(event_type, {
            "slug": slug,
            "payload_size": len(str(payload)),
            "has_slug": slug is not None
        })

    except Exception:
        # Silent failure
        pass

if __name__ == "__main__":
    main()