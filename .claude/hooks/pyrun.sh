#!/bin/sh
# Platform-independent Python resolver. Prefers python3, falls back to python.
cmd=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
if [ -z "$cmd" ]; then
    echo '{"ok": false, "reason": "Python interpreter not found. Install python3."}'
    exit 0
fi
exec "$cmd" "$@"
