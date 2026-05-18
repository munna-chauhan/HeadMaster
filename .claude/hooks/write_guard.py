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
"""PreToolUse/Write hook — blocks or warns on writes containing secret patterns.

CRITICAL_PATTERNS → deny (exit 0 with permissionDecision: deny)
MEDIUM_PATTERNS   → warn (exit 0 with additionalContext)
"""
import json
import re
import sys

# Definite secrets — block write
CRITICAL_PATTERNS = [
    r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
    r'(?i)(aws_secret_access_key|aws_access_key_id)\s*[:=]\s*\S+',
    r'(?i)(access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*["\']?\S{20,}',
    r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[A-Za-z0-9+/]{20,}',
]

# Likely false positives in docs/tests — warn only
MEDIUM_PATTERNS = [
    r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']?\S{8,}',
]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    content = payload.get("tool_input", {}).get("content", "")

    for pattern in CRITICAL_PATTERNS:
        if re.search(pattern, content):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "[CRITICAL] Secret pattern detected in write content. Remove before proceeding.",
                }
            }))
            sys.exit(0)

    for pattern in MEDIUM_PATTERNS:
        if re.search(pattern, content):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "[MEDIUM] Possible password/secret pattern in write content. Verify this is intentional (docs/tests are OK).",
                }
            }))
            sys.exit(0)


if __name__ == "__main__":
    main()
