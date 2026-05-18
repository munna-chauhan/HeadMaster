#!/bin/sh
# Platform-independent Python resolver with cached lookup.
# Cache file: .claude/cache/python-interpreter (gitignored).
# On cache hit and executable still valid → exec it directly.
# On miss/stale → probe python3 → py3 → python → py, write cache, exec.
# Strips the project bin/ shim directory from PATH to prevent recursion.

SELF="$0"
case "$SELF" in
    /*) ;;
    *) SELF="$PWD/$SELF" ;;
esac
SELF_DIR="${SELF%/*}"

SHIM_DIR=""
if [ -d "$SELF_DIR/../../bin" ]; then
    SHIM_DIR=$(cd "$SELF_DIR/../../bin" 2>/dev/null && pwd) || SHIM_DIR="$SELF_DIR/../../bin"
fi

if [ -n "$SHIM_DIR" ]; then
    export HEADMASTER_ORIG_PATH="${HEADMASTER_ORIG_PATH:-$PATH}"
    _new_path=""
    _saved_ifs="$IFS"
    IFS=":"
    for _p in $PATH; do
        [ "$_p" = "$SHIM_DIR" ] && continue
        _new_path="${_new_path:+$_new_path:}$_p"
    done
    IFS="$_saved_ifs"
    PATH="$_new_path"
fi

HM_ROOT=$(cd "$SELF_DIR/../.." 2>/dev/null && pwd) || HM_ROOT="$SELF_DIR/../.."
CACHE_DIR="$HM_ROOT/.claude/cache"
CACHE_FILE="$CACHE_DIR/python-interpreter"

if [ -f "$CACHE_FILE" ]; then
    cached=""
    read -r cached < "$CACHE_FILE" 2>/dev/null || cached=""
    if [ -n "$cached" ] && [ -x "$cached" ]; then
        exec "$cached" "$@"
    fi
fi

cmd=""
for candidate in python3 py3 python py; do
    cmd=$(command -v "$candidate" 2>/dev/null) && [ -n "$cmd" ] && break
    cmd=""
done
if [ -z "$cmd" ]; then
    echo '{"ok": false, "reason": "Python interpreter not found. Install python3, py3, python, or py."}'
    exit 0
fi

mkdir -p "$CACHE_DIR" 2>/dev/null && printf '%s\n' "$cmd" > "$CACHE_FILE" 2>/dev/null

exec "$cmd" "$@"
