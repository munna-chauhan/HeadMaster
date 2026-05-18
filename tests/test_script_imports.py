#!/usr/bin/env python
"""
Test all Python scripts for import errors and basic syntax.
"""

import importlib.util
import sys
from pathlib import Path


def test_script_imports():
    """Test importing all Python scripts"""
    scripts_dir = Path(__file__).parent
    errors = []
    success = []

    print("Testing Script Imports")
    print("=" * 60)

    # Test main scripts
    for script in sorted(scripts_dir.glob("*.py")):
        if script.name.startswith("__") or script.name == Path(__file__).name:
            continue

        try:
            spec = importlib.util.spec_from_file_location(script.stem, script)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[script.stem] = module
                # Don't execute main() - just test import
                success.append(script.name)
                print(f"[OK] {script.name}")
        except Exception as e:
            errors.append((script.name, str(e)))
            print(f"[FAIL] {script.name}: {e}")

    # Test archive scripts
    archive_dir = scripts_dir / "archive"
    if archive_dir.exists():
        print()
        print("Archive scripts:")
        for script in sorted(archive_dir.glob("*.py")):
            if script.name.startswith("__"):
                continue

            try:
                spec = importlib.util.spec_from_file_location(script.stem, script)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[script.stem] = module
                    success.append(f"archive/{script.name}")
                    print(f"[OK] archive/{script.name}")
            except Exception as e:
                errors.append((f"archive/{script.name}", str(e)))
                print(f"[FAIL] archive/{script.name}: {e}")

    print()
    print("=" * 60)
    print(f"Results: {len(success)} passed, {len(errors)} failed")

    if errors:
        print()
        print("Failed scripts:")
        for name, error in errors:
            print(f"  - {name}: {error}")
    assert not errors, f"{len(errors)} script(s) failed to import"


if __name__ == "__main__":
    try:
        test_script_imports()
        sys.exit(0)
    except Exception:
        sys.exit(1)
