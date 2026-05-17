#!/bin/sh
# Platform-independent Python resolver: python3 → python → py.
# Strips the project bin/ shim directory from PATH so we resolve to a system
# interpreter (otherwise bin/python → pyrun.sh → bin/python recurses).
# Uses only POSIX shell builtins so the resolver works even on a PATH that
# lacks dirname/tr/grep/sed.

# Resolve own dir without `dirname`.
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
    # POSIX in-shell PATH strip (no tr/grep/sed).
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

cmd=""
for candidate in python3 python py; do
    cmd=$(command -v "$candidate" 2>/dev/null) && [ -n "$cmd" ] && break
    cmd=""
done
if [ -z "$cmd" ]; then
    echo '{"ok": false, "reason": "Python interpreter not found. Install python3, python, or py."}'
    exit 0
fi
exec "$cmd" "$@"
