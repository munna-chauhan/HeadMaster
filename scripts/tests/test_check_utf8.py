#!/bin/sh
""":"
for c in python3 py3 python py; do command -v "$c" >/dev/null 2>&1 && exec "$c" "$0" "$@"; done
for d in /c/Python* /c/Python*/Python* "/c/Program Files/Python"* "/c/Program Files/Python"*/Python* "/c/Program Files (x86)/Python"* "/c/Program Files (x86)/Python"*/Python* "$HOME/AppData/Local/Programs/Python/Python"* "$LOCALAPPDATA/Programs/Python/Python"*; do
  for n in python.exe python3.exe; do
    [ -x "$d/$n" ] && exec "$d/$n" "$0" "$@"
  done
done
echo "[HeadMaster] No python interpreter found" >&2
exit 127
":"""
"""Tests for check_utf8.py."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_utf8 import has_mojibake, _MARKER

_TMP = Path(tempfile.mkdtemp())


def _write(name: str, content: str, encoding: str = "utf-8") -> Path:
    p = _TMP / name
    p.write_text(content, encoding=encoding)
    return p


def test_clean_file():
    p = _write("clean.md", "# Clean document\nNo issues here.\n")
    assert not has_mojibake(p)
    print("[PASS] clean file: no mojibake")


def test_mojibake_detected():
    # Write a file containing the marker sequence (built at runtime)
    p = _write("dirty.md", f"Some text {_MARKER}\x99 more text\n")
    assert has_mojibake(p)
    print("[PASS] mojibake detected")


def test_non_text_extension_skipped():
    p = _TMP / "binary.bin"
    p.write_bytes(b"\xe2\x80\x99 garbage bytes")
    assert not has_mojibake(p)
    print("[PASS] non-text extension skipped")


def test_missing_file():
    p = _TMP / "nonexistent.md"
    assert not has_mojibake(p)
    print("[PASS] missing file returns False")


def test_py_extension_checked():
    p = _write("script.py", "x = 'hello'\n")
    assert not has_mojibake(p)
    print("[PASS] .py extension is checked (clean)")


def test_yml_extension_checked():
    p = _write("config.yml", "key: value\n")
    assert not has_mojibake(p)
    print("[PASS] .yml extension is checked (clean)")


def test_marker_in_py_file():
    p = _write("script.py", f"# comment with {_MARKER}\x9c issue\n")
    assert has_mojibake(p)
    print("[PASS] mojibake in .py file detected")


if __name__ == "__main__":
    test_clean_file()
    test_mojibake_detected()
    test_non_text_extension_skipped()
    test_missing_file()
    test_py_extension_checked()
    test_yml_extension_checked()
    test_marker_in_py_file()
    print("\n[PASS] All check_utf8 tests passed")
