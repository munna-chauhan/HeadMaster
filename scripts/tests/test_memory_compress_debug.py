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
"""Debug memory file compression"""

from pathlib import Path
import sys
import re

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.compress import NEVER_COMPRESS, NEVER_COMPRESS_PATTERNS

test_path = "memory/features/acme/data-migration/status.md"
path = Path(test_path)

print(f"Testing: {test_path}")
print(f"Filename: {path.name}")
print()

print("Step 1: Check NEVER_COMPRESS set")
in_never = path.name in NEVER_COMPRESS
print(f"  {path.name} in NEVER_COMPRESS: {in_never}")
print()

print("Step 2: Check NEVER_COMPRESS_PATTERNS")
for i, pattern in enumerate(NEVER_COMPRESS_PATTERNS):
    match = pattern.match(path.name)
    print(f"  Pattern {i}: {pattern.pattern}")
    print(f"    Match: {match}")
print()

print("Step 3: Check path patterns")
COMPRESS_PATH_PATTERNS = [
    re.compile(r"(^|[/\\])memory[/\\]"),
    re.compile(r"[/\\]input[/\\].*\.md$"),
]
for i, pattern in enumerate(COMPRESS_PATH_PATTERNS):
    match = pattern.search(str(path))
    print(f"  Pattern {i}: {pattern.pattern}")
    print(f"    Search in: {str(path)}")
    print(f"    Match: {match}")
print()

# Final verdict
from scripts.compress import NEVER_COMPRESS, NEVER_COMPRESS_PATTERNS
if path.name in NEVER_COMPRESS:
    print("RESULT: SKIP (in NEVER_COMPRESS)")
elif any(p.match(path.name) for p in NEVER_COMPRESS_PATTERNS):
    print("RESULT: SKIP (matches NEVER_COMPRESS_PATTERNS)")
elif any(p.search(str(path)) for p in COMPRESS_PATH_PATTERNS):
    print("RESULT: COMPRESS (matches path pattern)")
else:
    print("RESULT: SKIP (no path pattern match)")
