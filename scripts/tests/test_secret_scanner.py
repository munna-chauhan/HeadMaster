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
"""Tests for secret_scanner.py — encoding/mojibake detection and scan_file integration."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from secret_scanner import _scan_encoding, _MOJIBAKE_MARKER, scan_file

_TMP = Path(tempfile.mkdtemp())


def _write(name: str, content: str) -> Path:
    p = _TMP / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Encoding / mojibake detection
# ---------------------------------------------------------------------------

def test_clean_file():
    p = _write("clean.md", "# Clean document\nNo issues here.\n")
    assert _scan_encoding(p, p.read_text(encoding="utf-8")) == []


def test_mojibake_detected():
    p = _write("dirty.md", f"Some text {_MOJIBAKE_MARKER}\x99 more text\n")
    assert _scan_encoding(p, p.read_text(encoding="utf-8")) != []


def test_non_text_extension_skipped():
    p = _TMP / "binary.bin"
    p.write_bytes(b"\xe2\x80\x99 garbage bytes")
    content = p.read_bytes().decode("utf-8", errors="ignore")
    assert _scan_encoding(p, content) == []


def test_missing_file_returns_empty():
    p = _TMP / "nonexistent.md"
    assert _scan_encoding(p, "") == []


def test_py_extension_checked_clean():
    p = _write("script.py", "x = 'hello'\n")
    assert _scan_encoding(p, p.read_text(encoding="utf-8")) == []


def test_yml_extension_checked_clean():
    p = _write("config.yml", "key: value\n")
    assert _scan_encoding(p, p.read_text(encoding="utf-8")) == []


def test_mojibake_in_py_file():
    p = _write("script.py", f"# comment with {_MOJIBAKE_MARKER}\x9c issue\n")
    assert _scan_encoding(p, p.read_text(encoding="utf-8")) != []


# ---------------------------------------------------------------------------
# scan_file integration — encoding findings surface through the main path
# ---------------------------------------------------------------------------

def test_scan_file_surfaces_encoding_finding():
    p = _write("mojibake.md", f"title: {_MOJIBAKE_MARKER}\x93corrupted\n")
    findings = scan_file(str(p))
    assert any(f.pattern_name == "Encoding/Mojibake" for f in findings)


def test_scan_file_clean_file_no_findings():
    p = _write("normal.md", "# Normal\nNo secrets or encoding issues.\n")
    findings = scan_file(str(p))
    assert findings == []
