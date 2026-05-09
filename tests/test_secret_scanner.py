"""Tests for scripts/secret_scanner.py."""

import tempfile

from scripts.secret_scanner import scan_file


class TestSecretScanner:
    def test_detects_aws_key(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
            f.flush()
            findings = scan_file(f.name)
        assert len(findings) >= 1
        assert any("AWS" in f.pattern_name for f in findings)

    def test_detects_generic_secret(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("password = 'SuperSecret123!'\n")
            f.flush()
            findings = scan_file(f.name)
        assert len(findings) >= 1

    def test_detects_jwt(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(f'token = "{jwt}"\n')
            f.flush()
            findings = scan_file(f.name)
        assert len(findings) >= 1

    def test_detects_connection_string(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('DB_URL = "postgres://admin:secret@db.example.com:5432/mydb"\n')
            f.flush()
            findings = scan_file(f.name)
        assert len(findings) >= 1

    def test_clean_file_no_findings(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    return 'world'\n")
            f.flush()
            findings = scan_file(f.name)
        assert len(findings) == 0

    def test_nonexistent_file(self):
        findings = scan_file("/nonexistent/path.py")
        assert findings == []

    def test_finding_has_redacted_snippet(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
            f.flush()
            findings = scan_file(f.name)
        if findings:
            assert "[REDACTED]" in findings[0].snippet
