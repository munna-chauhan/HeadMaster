#!/usr/bin/env python
"""SubagentStop hook — validate subagent produced expected output.

Checks that review-agent and qa-engineer subagents returned a verdict.
Prevents silent failures where subagent finishes without producing a result.
"""

import json
import re
import sys


VERDICT_KEYWORDS = {"APPROVED", "CONDITIONAL", "REJECTED", "PASS", "FINDINGS",
                    "BLOCKED", "APPROVED_PARTIAL", "REJECTED-BUG"}


def main():
    try:
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        sys.exit(0)

    last_msg = payload.get("last_assistant_message", "")
    if not last_msg or len(last_msg) < 20:
        print(json.dumps({"ok": False, "reason": "Subagent returned empty or too-short output"}))
        sys.exit(0)

    # Check for verdict in output
    has_verdict = any(kw in last_msg for kw in VERDICT_KEYWORDS)

    # Check for greenfield (codebase-analyst valid output)
    has_greenfield = "greenfield" in last_msg.lower()

    # Check for structured table (codebase-analyst valid output)
    has_table = "|" in last_msg and last_msg.count("|") >= 4

    if has_verdict or has_greenfield or has_table:
        print(json.dumps({"ok": True}))
    else:
        print(json.dumps({
            "ok": False,
            "reason": "Subagent output missing verdict or structured result"
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
