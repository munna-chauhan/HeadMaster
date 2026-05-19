#!/bin/sh
""":"
for c in python3 py3 python py; do command -v "$c" >/dev/null 2>&1 && exec "$c" "$0" "$@"; done
for d in /c/Python* /c/Python*/Python* "/c/Program Files/Python"* "/c/Program Files/Python"*/Python* "/c/Program Files (x86)/Python"* "/c/Program Files (x86)/Python"*/Python* "$HOME/AppData/Local/Programs/Python/Python"* "$LOCALAPPDATA/Programs/Python/Python"*; do
  for n in python.exe python3.exe; do
    [ -x "$d/$n" ] && exec "$d/$n" "$0" "$@"
  done
done
echo "[HeadMaster] No python interpreter found" >&2
exit 127
":"""
"""
check_utf8.py -- Pre-commit hook: reject commits containing mojibake markers.

CP1252 round-trip corruption produces predictable multi-byte sequences that are
valid UTF-8 but visually wrong. The two-byte prefix b'\xe2\x80' decoded as CP1252
yields the euro-sign sequence that appears in all common markers.

Usage (pre-commit hook, staged files):
  git diff --cached --name-only -z | xargs -0 sh scripts/check_utf8.py

Usage (explicit paths):
  sh scripts/check_utf8.py <file1> [file2 ...]

Exit 0: clean. Exit 1: mojibake found.
"""
import sys
from pathlib import Path

# Build the marker at runtime so this file stays clean ASCII.
# b'\xe2\x80' decoded as CP1252 yields the 2-char string that prefixes every
# common mojibake sequence (right/left quotes, dashes, ellipsis, arrows).
_MARKER = b"\xe2\x80".decode("cp1252")

TEXT_EXTENSIONS = frozenset({".py", ".md", ".yml", ".yaml", ".json", ".txt", ".sh", ".xml"})


def has_mojibake(path: Path) -> bool:
    if path.suffix not in TEXT_EXTENSIONS:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    return _MARKER in text


def main():
    paths = [Path(p) for p in sys.argv[1:] if p.strip()]
    if not paths:
        sys.exit(0)

    bad = [p for p in paths if p.exists() and has_mojibake(p)]
    if not bad:
        sys.exit(0)

    print("[check_utf8] Mojibake markers in staged files -- commit blocked:", file=sys.stderr)
    for p in bad:
        print(f"  {p}", file=sys.stderr)
    print("  Fix: sh scripts/oneshot/fix_mojibake.py <file>", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
