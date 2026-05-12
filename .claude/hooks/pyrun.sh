#!/bin/sh
# Platform-independent Python resolver. Prefers python, falls back to python.
cmd=$(command -v python 2>/dev/null || command -v python 2>/dev/null)
if [ -z "$cmd" ]; then
    echo '{"ok": false, "reason": "Python interpreter not found. Install python."}'
    exit 0
fi
exec "$cmd" "$@"
