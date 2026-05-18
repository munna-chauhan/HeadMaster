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
"""Test memory pattern bug"""

import re

# Current pattern from read_compressor.py
pattern = re.compile(r"[/\\]memory[/\\]")

test_cases = [
    'memory/features/acme/status.md',  # at root - THIS IS THE BUG
    'docs/memory/status.md',  # with prefix
    r'memory\features\acme\status.md',  # Windows style at root
]

print(f'Pattern: {pattern.pattern}')
print('Looking for separator BEFORE "memory" and AFTER "memory"')
print()

for test in test_cases:
    match = pattern.search(test)
    print(f'Test: {test:45s} -> {"MATCH" if match else "NO MATCH"}')

print()
print('ISSUE: memory/ at root has no leading separator!')
print()
print('Fixed pattern should be: r"(^|[/\\\\])memory[/\\\\]"')

# Test fixed pattern
fixed_pattern = re.compile(r"(^|[/\\])memory[/\\]")
print()
print(f'Fixed pattern: {fixed_pattern.pattern}')
for test in test_cases:
    match = fixed_pattern.search(test)
    print(f'Test: {test:45s} -> {"MATCH" if match else "NO MATCH"}')
