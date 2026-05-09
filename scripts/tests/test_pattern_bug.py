#!/usr/bin/env python
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
