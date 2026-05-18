#!/usr/bin/env python
"""
Regression test suite for HeadMaster refactoring.
Tests critical paths after docs/projects → docs/features migration.
"""

import sys
import yaml
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config_utils import ConfigResolver


def test_config_loading():
    """Test config.yml loads and structure is valid"""
    print("Test: Config Loading")
    config_path = Path(__file__).parent.parent / "config.yml"

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "projects" in config, "Missing projects key"
    assert "active" in config["projects"], "Missing active project"
    assert "pipeline" in config, "Missing pipeline config"

    active = config["projects"]["active"]
    assert active in config["projects"], f"Active project '{active}' not defined"

    print(f"  [OK] Active project: {active}")
    print(f"  [OK] Projects defined: {[k for k in config['projects'].keys() if k != 'active']}")


def test_directory_structure():
    """Test directory structure matches new paths"""
    print("\nTest: Directory Structure")
    repo_root = Path(__file__).parent.parent

    # Check docs/features exists
    docs_features = repo_root / "docs" / "features"
    assert docs_features.exists(), f"docs/features/ not found"
    print(f"  [OK] docs/features/ exists")

    # Check memory/features exists
    memory_features = repo_root / "memory" / "features"
    assert memory_features.exists(), f"memory/features/ not found"
    print(f"  [OK] memory/features/ exists")

    # Check no old paths exist
    old_docs = repo_root / "docs" / "projects"
    assert not old_docs.exists(), f"Old docs/projects/ still exists - should be removed"
    print(f"  [OK] Old docs/projects/ cleaned up")


def test_project_paths():
    """Test project-specific paths resolve correctly"""
    print("\nTest: Project Path Resolution")
    resolver = ConfigResolver()

    for project in ["acme", "beta"]:
        # Check features path
        features = resolver.get_features_path(project)
        expected = resolver.hm_root / "docs" / "features" / project
        assert features == expected, f"Features path mismatch for {project}"

        # Check feature memory path
        test_slug = "test-feature"
        memory = resolver.get_feature_memory_path(test_slug, project)
        expected_mem = resolver.hm_root / "memory" / "features" / project / test_slug
        assert memory == expected_mem, f"Memory path mismatch for {project}"

        print(f"  [OK] {project}: paths resolve correctly")


def test_feature_discovery():
    """Test feature discovery in new structure"""
    print("\nTest: Feature Discovery")
    resolver = ConfigResolver()

    features_root = resolver.get_features_path()
    if features_root.exists():
        features = [d.name for d in features_root.iterdir() if d.is_dir()]
        if features:
            print(f"  [OK] Found {len(features)} features in active project")
            for slug in features[:3]:  # Show first 3
                print(f"       - {slug}")
        else:
            print(f"  [OK] No features yet (expected for new setup)")
    else:
        print(f"  [OK] Features directory will be created on first use")


def test_backwards_compatibility():
    """Test that old references are cleaned up"""
    print("\nTest: Old Path References Cleaned Up")
    repo_root = Path(__file__).parent.parent

    # Check key files don't reference old paths
    files_to_check = [
        repo_root / ".claude" / "CLAUDE.md",
        repo_root / "scripts" / "config_utils.py",
        repo_root / "config.yml",
    ]

    issues = []
    for filepath in files_to_check:
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")
        if "docs/projects/" in content:
            issues.append(f"{filepath.name}: contains 'docs/projects/'")

    assert not issues, "Old path references found: " + "; ".join(issues)
    print(f"  [OK] No old path references found")


def run_all_tests():
    """Run all regression tests"""
    print("=" * 60)
    print("HeadMaster Regression Test Suite")
    print("=" * 60)
    print()

    tests = [
        test_config_loading,
        test_directory_structure,
        test_project_paths,
        test_feature_discovery,
        test_backwards_compatibility,
    ]

    results = []
    for test in tests:
        try:
            test()
            results.append((test.__name__, True))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append((test.__name__, False))

    print()
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed < total:
        print("\nFailed tests:")
        for name, result in results:
            if not result:
                print(f"  - {name}")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
