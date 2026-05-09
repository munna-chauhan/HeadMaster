#!/usr/bin/env python
"""Test compression path patterns"""

from pathlib import Path
import sys
import re

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.compress import NEVER_COMPRESS, NEVER_COMPRESS_PATTERNS

# Load patterns from read_compressor.py
COMPRESS_PATH_PATTERNS = [
    re.compile(r"(^|[/\\])memory[/\\]"),
    re.compile(r"[/\\]input[/\\].*\.md$"),
]

def is_compressible(path: Path) -> bool:
    """Matches logic from read_compressor.py"""
    if path.name in NEVER_COMPRESS:
        return False
    if any(p.match(path.name) for p in NEVER_COMPRESS_PATTERNS):
        return False
    return any(p.search(str(path)) for p in COMPRESS_PATH_PATTERNS)

test_paths = [
    'docs/features/acme/data-migration/planning/PRD.md',
    'docs/features/acme/data-migration/design/TDD_DESIGN.md',
    'docs/features/acme/data-migration/breakdown/JIRA_BREAKDOWN.md',
    'memory/features/acme/data-migration/status.md',
    'memory/features/acme/data-migration/handoff-001.md',
    'docs/features/acme/data-migration/input/requirements.md',
]

print('Testing full compression logic (filename + path):')
print()
for p in test_paths:
    path = Path(p)
    result = is_compressible(path)
    print(f'  {p:70s} -> {"COMPRESS" if result else "SKIP"}')
