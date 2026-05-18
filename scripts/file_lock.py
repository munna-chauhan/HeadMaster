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
"""Shared file locking — Windows msvcrt / Unix fcntl.

Locks are OS-level and auto-release on process exit.
acquire() uses a timeout to handle hung processes holding locks.
"""
import platform
import time

if platform.system() == "Windows":
    import msvcrt
else:
    import fcntl

DEFAULT_TIMEOUT = 30


def acquire(fh, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Acquire file lock. Raises TimeoutError if lock not acquired within timeout."""
    deadline = time.time() + timeout
    while True:
        try:
            if platform.system() == "Windows":
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except (IOError, OSError):
            if time.time() > deadline:
                raise TimeoutError(
                    f"Could not acquire lock on {fh.name} within {timeout}s — "
                    f"another process may be hung. Check for stuck gate_transition or story_phase_complete processes."
                )
            time.sleep(0.5)


def release(fh) -> None:
    if platform.system() == "Windows":
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
