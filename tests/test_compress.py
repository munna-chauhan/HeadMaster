#!/usr/bin/env python3
"""Tests for the compress subsystem: detect, validate, and compress modules."""

# ---------------------------------------------------------------------------
# We add the repo root to sys.path so `compress` is importable as a package.
# ---------------------------------------------------------------------------
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from compress.detect import (
    _is_code_line,
    _is_json_content,
    _is_yaml_content,
    detect_file_type,
    should_compress,
)
from compress.validate import (
    ValidationResult,
    count_bullets,
    extract_code_blocks,
    extract_headings,
    extract_paths,
    extract_urls,
    validate,
    validate_code_blocks,
    validate_headings,
    validate_urls,
)
from compress.compress import (
    SENSITIVE_BASENAME_REGEX,
    is_sensitive_path,
    strip_llm_wrapper,
)


# ===================================================================
# detect.py tests
# ===================================================================


class TestDetectFileType:
    """Tests for detect_file_type()."""

    def test_markdown_extension(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# Hello\nSome notes here.")
        assert detect_file_type(f) == "natural_language"

    def test_txt_extension(self, tmp_path):
        f = tmp_path / "readme.txt"
        f.write_text("Just some text.")
        assert detect_file_type(f) == "natural_language"

    def test_rst_extension(self, tmp_path):
        f = tmp_path / "docs.rst"
        f.write_text("Title\n=====\nContent here.")
        assert detect_file_type(f) == "natural_language"

    def test_python_extension(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("import os\nprint('hello')")
        assert detect_file_type(f) == "code"

    def test_javascript_extension(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const x = 1;")
        assert detect_file_type(f) == "code"

    def test_json_extension(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"key": "value"}')
        assert detect_file_type(f) == "config"

    def test_yaml_extension(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("key: value")
        assert detect_file_type(f) == "config"

    def test_env_extension(self, tmp_path):
        f = tmp_path / "secrets.env"
        f.write_text("API_KEY=abc123")
        assert detect_file_type(f) == "config"

    def test_unknown_extension(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("random stuff")
        assert detect_file_type(f) == "unknown"

    def test_extensionless_natural_language(self, tmp_path):
        f = tmp_path / "README"
        f.write_text("# Project\n\nThis is a project readme with natural language.")
        assert detect_file_type(f) == "natural_language"

    def test_extensionless_code(self, tmp_path):
        f = tmp_path / "Makefile"
        # Write content that looks like code (>40% code lines)
        f.write_text(
            "import os\n"
            "from pathlib import Path\n"
            "def main():\n"
            "    pass\n"
            "class Foo:\n"
            "    pass\n"
        )
        assert detect_file_type(f) == "code"

    def test_extensionless_json(self, tmp_path):
        f = tmp_path / "lockfile"
        f.write_text('{"packages": {"a": "1.0"}}')
        assert detect_file_type(f) == "config"

    def test_extensionless_yaml(self, tmp_path):
        f = tmp_path / "config"
        f.write_text(
            "---\n"
            "name: myapp\n"
            "version: 1.0\n"
            "database: postgres\n"
            "host: localhost\n"
            "port: 5432\n"
        )
        assert detect_file_type(f) == "config"


class TestShouldCompress:
    """Tests for should_compress()."""

    def test_markdown_file(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# Notes\nSome content.")
        assert should_compress(f) is True

    def test_python_file(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("print('hello')")
        assert should_compress(f) is False

    def test_backup_file(self, tmp_path):
        f = tmp_path / "notes.original.md"
        f.write_text("# Notes\nOriginal content.")
        assert should_compress(f) is False

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "missing.md"
        assert should_compress(f) is False

    def test_directory(self, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        assert should_compress(d) is False

    def test_json_file(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text('{"name": "test"}')
        assert should_compress(f) is False


class TestCodeLineDetection:
    """Tests for _is_code_line()."""

    def test_import_statement(self):
        assert _is_code_line("import os") is True

    def test_from_import(self):
        assert _is_code_line("from pathlib import Path") is True

    def test_function_def(self):
        assert _is_code_line("def main():") is True

    def test_class_def(self):
        assert _is_code_line("class MyClass:") is True

    def test_natural_language(self):
        assert _is_code_line("This is a regular sentence.") is False

    def test_heading(self):
        assert _is_code_line("# Some heading") is False

    def test_closing_braces(self):
        assert _is_code_line("  })") is True

    def test_decorator(self):
        assert _is_code_line("@property") is True


class TestJsonDetection:
    """Tests for _is_json_content()."""

    def test_valid_json(self):
        assert _is_json_content('{"key": "value"}') is True

    def test_invalid_json(self):
        assert _is_json_content("not json at all") is False

    def test_json_array(self):
        assert _is_json_content('[1, 2, 3]') is True

    def test_empty_string(self):
        assert _is_json_content("") is False


class TestYamlDetection:
    """Tests for _is_yaml_content()."""

    def test_yaml_content(self):
        lines = ["---", "name: myapp", "version: 1.0", "port: 8080"]
        assert _is_yaml_content(lines) is True

    def test_not_yaml(self):
        lines = ["# Heading", "Some paragraph text", "More text here"]
        assert _is_yaml_content(lines) is False

    def test_empty_lines(self):
        lines = []
        assert _is_yaml_content(lines) is False


# ===================================================================
# validate.py tests
# ===================================================================


class TestExtractHeadings:
    """Tests for extract_headings()."""

    def test_single_heading(self):
        text = "# Hello World"
        assert extract_headings(text) == [("#", "Hello World")]

    def test_multiple_headings(self):
        text = "# Title\n## Section\n### Sub"
        result = extract_headings(text)
        assert len(result) == 3
        assert result[0] == ("#", "Title")
        assert result[1] == ("##", "Section")
        assert result[2] == ("###", "Sub")

    def test_no_headings(self):
        text = "Just some text\nwithout any headings."
        assert extract_headings(text) == []

    def test_heading_with_extra_spaces(self):
        text = "# Title with spaces  "
        result = extract_headings(text)
        assert result[0] == ("#", "Title with spaces")


class TestExtractCodeBlocks:
    """Tests for extract_code_blocks()."""

    def test_single_code_block(self):
        text = "text\n```python\nprint('hi')\n```\nmore text"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "print('hi')" in blocks[0]

    def test_multiple_code_blocks(self):
        text = "```js\nconst x = 1;\n```\ntext\n```py\ny = 2\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2

    def test_no_code_blocks(self):
        text = "Just plain text without any code."
        assert extract_code_blocks(text) == []

    def test_tilde_fence(self):
        text = "~~~\ncode here\n~~~"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1

    def test_unclosed_fence(self):
        text = "```python\nprint('hi')\nno closing fence"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 0  # unclosed fences are skipped

    def test_nested_fences(self):
        text = "````\nsome\n```\ninner\n```\nmore\n````"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1  # outer fence captures everything


class TestExtractUrls:
    """Tests for extract_urls()."""

    def test_http_url(self):
        text = "Visit http://example.com for info."
        assert "http://example.com" in extract_urls(text)

    def test_https_url(self):
        text = "See https://docs.python.org/3/"
        urls = extract_urls(text)
        assert any("docs.python.org" in u for u in urls)

    def test_multiple_urls(self):
        text = "Go to https://a.com and https://b.com"
        urls = extract_urls(text)
        assert len(urls) == 2

    def test_no_urls(self):
        text = "No links here at all."
        assert extract_urls(text) == set()


class TestExtractPaths:
    """Tests for extract_paths()."""

    def test_relative_path(self):
        text = "Edit the file at ./src/main.py"
        paths = extract_paths(text)
        assert any("src/main.py" in p for p in paths)

    def test_absolute_path(self):
        text = "Located at /usr/local/bin/python"
        paths = extract_paths(text)
        assert any("/usr/local/bin/python" in p for p in paths)

    def test_no_paths(self):
        text = "No file paths here."
        assert extract_paths(text) == set()


class TestCountBullets:
    """Tests for count_bullets()."""

    def test_dash_bullets(self):
        text = "- item 1\n- item 2\n- item 3"
        assert count_bullets(text) == 3

    def test_asterisk_bullets(self):
        text = "* item 1\n* item 2"
        assert count_bullets(text) == 2

    def test_plus_bullets(self):
        text = "+ item 1\n+ item 2"
        assert count_bullets(text) == 2

    def test_no_bullets(self):
        text = "Just a paragraph."
        assert count_bullets(text) == 0

    def test_mixed_bullets(self):
        text = "- dash\n* star\n+ plus"
        assert count_bullets(text) == 3


class TestValidateHeadings:
    """Tests for validate_headings()."""

    def test_matching_headings(self):
        orig = "# Title\n## Section"
        comp = "# Title\n## Section"
        result = ValidationResult()
        validate_headings(orig, comp, result)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_heading(self):
        orig = "# Title\n## Section\n## Another"
        comp = "# Title\n## Section"
        result = ValidationResult()
        validate_headings(orig, comp, result)
        assert result.is_valid is False

    def test_changed_heading_text(self):
        orig = "# Original Title"
        comp = "# Changed Title"
        result = ValidationResult()
        validate_headings(orig, comp, result)
        # Heading count matches (1 == 1) but text differs -> warning only
        assert len(result.warnings) > 0


class TestValidateCodeBlocks:
    """Tests for validate_code_blocks()."""

    def test_preserved_code(self):
        orig = "text\n```py\nprint('hi')\n```\nmore"
        comp = "shorter\n```py\nprint('hi')\n```\nless"
        result = ValidationResult()
        validate_code_blocks(orig, comp, result)
        assert result.is_valid is True

    def test_modified_code(self):
        orig = "text\n```py\nprint('hi')\n```"
        comp = "text\n```py\nprint('hello')\n```"
        result = ValidationResult()
        validate_code_blocks(orig, comp, result)
        assert result.is_valid is False


class TestValidateUrls:
    """Tests for validate_urls()."""

    def test_preserved_urls(self):
        orig = "See https://example.com for details."
        comp = "Check https://example.com for info."
        result = ValidationResult()
        validate_urls(orig, comp, result)
        assert result.is_valid is True

    def test_lost_url(self):
        orig = "Visit https://example.com and https://other.com"
        comp = "Visit https://example.com"
        result = ValidationResult()
        validate_urls(orig, comp, result)
        assert result.is_valid is False


class TestValidateIntegration:
    """Integration tests using file-based validation."""

    def test_identical_files(self, tmp_path):
        orig = tmp_path / "orig.md"
        comp = tmp_path / "comp.md"
        content = "# Title\n\nSome text.\n\n```py\nx = 1\n```\n\nhttps://example.com"
        orig.write_text(content)
        comp.write_text(content)
        result = validate(orig, comp)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_compressed_preserves_structure(self, tmp_path):
        orig = tmp_path / "orig.md"
        comp = tmp_path / "comp.md"
        orig.write_text(
            "# Project Notes\n\n"
            "## Architecture\n\n"
            "This is a detailed explanation.\n\n"
            "```python\nimport os\n```\n\n"
            "See https://docs.python.org\n"
        )
        comp.write_text(
            "# Project Notes\n\n"
            "## Architecture\n\n"
            "Detailed explanation.\n\n"
            "```python\nimport os\n```\n\n"
            "See https://docs.python.org\n"
        )
        result = validate(orig, comp)
        assert result.is_valid is True

    def test_missing_code_block_fails(self, tmp_path):
        orig = tmp_path / "orig.md"
        comp = tmp_path / "comp.md"
        orig.write_text("# Title\n\n```py\nx = 1\n```\n")
        comp.write_text("# Title\n\nCode removed.\n")
        result = validate(orig, comp)
        assert result.is_valid is False
        assert any("Code blocks" in e for e in result.errors)


# ===================================================================
# compress.py tests
# ===================================================================


class TestSensitivePathDetection:
    """Tests for is_sensitive_path()."""

    def test_env_file(self):
        assert is_sensitive_path(Path(".env")) is True

    def test_env_local(self):
        assert is_sensitive_path(Path(".env.local")) is True

    def test_credentials_file(self):
        assert is_sensitive_path(Path("credentials.json")) is True

    def test_secrets_file(self):
        assert is_sensitive_path(Path("secrets.md")) is True

    def test_ssh_key(self):
        assert is_sensitive_path(Path("id_rsa")) is True

    def test_ssh_key_pub(self):
        assert is_sensitive_path(Path("id_ed25519.pub")) is True

    def test_pem_file(self):
        assert is_sensitive_path(Path("server.pem")) is True

    def test_key_file(self):
        assert is_sensitive_path(Path("private.key")) is True

    def test_normal_markdown(self):
        assert is_sensitive_path(Path("HELP.md")) is False

    def test_normal_text(self):
        assert is_sensitive_path(Path("notes.txt")) is False

    def test_ssh_directory(self):
        assert is_sensitive_path(Path(".ssh/config")) is True

    def test_aws_directory(self):
        assert is_sensitive_path(Path(".aws/credentials")) is True

    def test_kube_directory(self):
        assert is_sensitive_path(Path(".kube/config")) is True

    def test_api_key_in_name(self):
        assert is_sensitive_path(Path("api-key.md")) is True

    def test_access_key_in_name(self):
        assert is_sensitive_path(Path("access_key.txt")) is True

    def test_token_in_name(self):
        assert is_sensitive_path(Path("auth-token.md")) is True

    def test_password_in_name(self):
        assert is_sensitive_path(Path("password.txt")) is True

    def test_netrc(self):
        assert is_sensitive_path(Path(".netrc")) is True

    def test_authorized_keys(self):
        assert is_sensitive_path(Path("authorized_keys")) is True

    def test_known_hosts(self):
        assert is_sensitive_path(Path("known_hosts")) is True

    def test_project_notes(self):
        assert is_sensitive_path(Path("project-notes.md")) is False

    def test_todo_list(self):
        assert is_sensitive_path(Path("todo-list.md")) is False


class TestStripLlmWrapper:
    """Tests for strip_llm_wrapper()."""

    def test_no_wrapper(self):
        text = "# Hello\nWorld"
        assert strip_llm_wrapper(text) == text

    def test_markdown_wrapper(self):
        text = "```markdown\n# Hello\nWorld\n```"
        assert strip_llm_wrapper(text) == "# Hello\nWorld"

    def test_plain_backtick_wrapper(self):
        text = "```\n# Hello\nWorld\n```"
        assert strip_llm_wrapper(text) == "# Hello\nWorld"

    def test_tilde_wrapper(self):
        text = "~~~\n# Hello\nWorld\n~~~"
        assert strip_llm_wrapper(text) == "# Hello\nWorld"

    def test_inner_code_blocks_preserved(self):
        # Only strips if the entire text is wrapped
        text = "Some text\n```py\nx = 1\n```\nMore text"
        assert strip_llm_wrapper(text) == text

    def test_empty_string(self):
        assert strip_llm_wrapper("") == ""

    def test_four_backtick_wrapper(self):
        text = "````\n# Hello\nWorld\n````"
        assert strip_llm_wrapper(text) == "# Hello\nWorld"


class TestSensitiveRegex:
    """Tests for SENSITIVE_BASENAME_REGEX pattern coverage."""

    def test_p12_file(self):
        assert SENSITIVE_BASENAME_REGEX.match("cert.p12") is not None

    def test_pfx_file(self):
        assert SENSITIVE_BASENAME_REGEX.match("cert.pfx") is not None

    def test_jks_file(self):
        assert SENSITIVE_BASENAME_REGEX.match("keystore.jks") is not None

    def test_gpg_file(self):
        assert SENSITIVE_BASENAME_REGEX.match("key.gpg") is not None

    def test_asc_file(self):
        assert SENSITIVE_BASENAME_REGEX.match("key.asc") is not None

    def test_regular_md(self):
        assert SENSITIVE_BASENAME_REGEX.match("HELP.md") is None

    def test_regular_py(self):
        assert SENSITIVE_BASENAME_REGEX.match("main.py") is None
