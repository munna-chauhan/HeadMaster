#!/usr/bin/env python
"""
Test path resolution across all scripts after refactoring.
Validates that docs/features/{project}/{slug} and memory paths resolve correctly.
"""

import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config_utils import ConfigResolver


def test_path_resolution():
    """Test all path resolution methods"""
    print("Testing Path Resolution")
    print("=" * 60)

    try:
        resolver = ConfigResolver()
        print(f"[OK] Config loaded successfully")
        print(f"  Active project: {resolver.active_project}")
        print()

        # Test features path
        features = resolver.get_features_path()
        expected_features = resolver.hm_root / "docs" / "features" / resolver.active_project
        assert features == expected_features, f"Features path mismatch: {features} != {expected_features}"
        print(f"[OK] Features path: {features}")
        print(f"  Expected: docs/features/{{project}}/")
        print(f"  Resolved: {features.relative_to(resolver.hm_root)}")
        print()

        # Test feature memory path
        test_slug = "test-feature"
        feature_memory = resolver.get_feature_memory_path(test_slug)
        expected_feature_memory = resolver.hm_root / "memory" / "features" / resolver.active_project / test_slug
        assert feature_memory == expected_feature_memory, f"Feature memory mismatch: {feature_memory} != {expected_feature_memory}"
        print(f"[OK] Feature memory: {feature_memory}")
        print(f"  Expected: memory/features/{{project}}/{{slug}}/")
        print(f"  Resolved: {feature_memory.relative_to(resolver.hm_root)}")
        print()

        # Test all projects
        print("Testing all configured projects:")
        projects = [k for k in resolver.config.get("projects", {}).keys() if k != "active"]
        for ws in projects:
            features_ws = resolver.get_features_path(ws)
            memory_ws = resolver.get_project_memory_path(ws)
            print(f"  {ws}:")
            print(f"    Features: {features_ws.relative_to(resolver.hm_root)}")
            print(f"    Memory:   {memory_ws.relative_to(resolver.hm_root)}")
        print()

        print("=" * 60)
        print("[OK] All path resolution tests passed!")
        return True

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_path_resolution()
    sys.exit(0 if success else 1)
