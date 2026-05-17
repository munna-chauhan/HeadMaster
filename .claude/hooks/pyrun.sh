#!/bin/sh
# Platform-independent Python resolver: python3 → python → py.
# Strips the project bin/ shim directory from PATH so we resolve to a system
# interpreter (otherwise bin/python → pyrun.sh → bin/python recurses).
SHIM_DIR="$(cd "$(dirname "$0")/../../bin" 2>/dev/null && pwd)"
if [ -n "$SHIM_DIR" ]; then
    # Stash original PATH so callees (e.g. activate.py preflight) can see how
    # the shell was invoked, then strip the shim dir for resolution.
    export HEADMASTER_ORIG_PATH="${HEADMASTER_ORIG_PATH:-$PATH}"
    PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -vx "$SHIM_DIR" | tr '\n' ':' | sed 's/:$//')
fi
for candidate in python3 python py; do
    cmd=$(command -v "$candidate" 2>/dev/null) && break
done
if [ -z "$cmd" ]; then
    echo '{"ok": false, "reason": "Python interpreter not found. Install python3, python, or py."}'
    exit 0
fi
exec "$cmd" "$@"
