#!/usr/bin/env python
"""Tests for memory_validator.py"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_validator import validate_memory_index, validate_memory_file


def test_memory_index_under_200_lines_passes(tmp_path):
    """Memory index under 200 lines passes validation."""
    memory_md = tmp_path / "MEMORY.md"
    memory_md.write_text("\n".join([f"- Memory entry {i}" for i in range(150)]), encoding="utf-8")

    result = validate_memory_index(memory_md)

    assert result["ok"] is True
    assert result["line_count"] == 150
    assert len(result["warnings"]) == 0


def test_memory_index_over_200_lines_warns(tmp_path):
    """Memory index over 200 lines triggers warning."""
    memory_md = tmp_path / "MEMORY.md"
    memory_md.write_text("\n".join([f"- Memory entry {i}" for i in range(250)]), encoding="utf-8")

    result = validate_memory_index(memory_md)

    assert result["ok"] is False
    assert result["line_count"] == 250
    assert len(result["warnings"]) == 1
    assert "exceeds 200 lines" in result["warnings"][0]


def test_memory_index_missing_file_errors(tmp_path):
    """Missing MEMORY.md file returns error."""
    memory_md = tmp_path / "MEMORY.md"

    result = validate_memory_index(memory_md)

    assert result["ok"] is False
    assert len(result["errors"]) == 1
    assert "not found" in result["errors"][0]


def test_memory_index_long_line_warns(tmp_path):
    """Very long lines in MEMORY.md trigger warning."""
    memory_md = tmp_path / "MEMORY.md"
    long_line = "- " + ("x" * 600)
    memory_md.write_text(long_line, encoding="utf-8")

    result = validate_memory_index(memory_md)

    assert len(result["warnings"]) >= 1
    assert "exceeds 500 characters" in result["warnings"][-1]


def test_memory_file_under_100kb_passes(tmp_path):
    """Memory file under 100KB passes validation."""
    memory_file = tmp_path / "user.md"
    content = "---\nname: test\ndescription: test\ntype: user\n---\n\n" + ("Content\n" * 1000)
    memory_file.write_text(content, encoding="utf-8")

    result = validate_memory_file(memory_file)

    assert result["ok"] is True
    assert result["size_kb"] < 100


def test_memory_file_over_100kb_warns(tmp_path):
    """Memory file over 100KB triggers warning."""
    memory_file = tmp_path / "feedback.md"
    content = "---\nname: test\ndescription: test\ntype: feedback\n---\n\n" + ("x" * 120000)
    memory_file.write_text(content, encoding="utf-8")

    result = validate_memory_file(memory_file)

    assert result["size_kb"] > 100
    assert len(result["warnings"]) >= 1
    assert "100KB" in result["warnings"][0] or "KB" in result["warnings"][0]


def test_memory_file_over_500kb_errors(tmp_path):
    """Memory file over 500KB triggers error."""
    memory_file = tmp_path / "project.md"
    content = "x" * 600000
    memory_file.write_text(content, encoding="utf-8")

    result = validate_memory_file(memory_file)

    assert result["ok"] is False
    assert result["size_kb"] > 500
    assert len(result["errors"]) >= 1
    assert "500KB" in result["errors"][0]


def test_memory_file_malformed_frontmatter_errors(tmp_path):
    """Memory file with unclosed frontmatter triggers error."""
    memory_file = tmp_path / "user.md"
    content = "---\nname: test\ndescription: test\ntype: user\n\nContent without closing ---"
    memory_file.write_text(content, encoding="utf-8")

    result = validate_memory_file(memory_file)

    assert result["ok"] is False
    assert any("unclosed frontmatter" in e for e in result["errors"])


def test_memory_file_missing_frontmatter_field_warns(tmp_path):
    """Memory file missing required frontmatter field warns."""
    memory_file = tmp_path / "feedback.md"
    content = "---\nname: test\n---\n\nContent"  # Missing description and type
    memory_file.write_text(content, encoding="utf-8")

    result = validate_memory_file(memory_file)

    assert len(result["warnings"]) >= 2
    assert any("description:" in w for w in result["warnings"])
    assert any("type:" in w for w in result["warnings"])


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
