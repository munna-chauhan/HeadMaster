#!/usr/bin/env python3
"""
Secret scanner for HeadMaster pipeline.

Scans files or git staged changes for leaked secrets (API keys, tokens, passwords).
Returns non-zero exit code if secrets found — blocks commit.

Usage:
    python3 scripts/secret_scanner.py --staged          # Scan staged files
    python3 scripts/secret_scanner.py --path src/       # Scan directory
    python3 scripts/secret_scanner.py --file config.py  # Scan single file
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:
    print("[ERROR] Missing dependency: pip install pyyaml")
    sys.exit(1)


def safe_run(cmd: List[str]) -> tuple[int, str, str]:
    """Run a subprocess safely, return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, "", str(e)


def _load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


@dataclass
class Finding:
    file: str
    line_num: int
    pattern_name: str
    snippet: str  # redacted snippet showing context


# Secret patterns: (name, regex, description)
_DEFAULT_PATTERNS = [
    ("AWS Access Key", r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    ("AWS Secret Key", r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[=:]\s*\S{20,}", "AWS secret access key"),
    ("Generic API Key", r"(?i)(api[_\-]?key|apikey)\s*[=:]\s*['\"][A-Za-z0-9_\-]{20,}['\"]", "Generic API key"),
    ("Generic Secret", r"(?i)(secret|password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{8,}['\"]", "Password or secret"),
    ("JWT Token", r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT token"),
    ("Private Key", r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "Private key file"),
    ("GitHub Token", r"gh[ps]_[A-Za-z0-9_]{36,}", "GitHub personal access token"),
    ("Slack Token", r"xox[baprs]-[0-9A-Za-z\-]{10,}", "Slack token"),
    ("Connection String", r"(?i)(postgres|mysql|mongodb|redis)://\S+:\S+@\S+", "Database connection string"),
    ("Bearer Token", r"(?i)bearer\s+[A-Za-z0-9_\-.]{20,}", "Bearer authorization token"),
]

# Values that are obviously test/example placeholders — never flag these
# Only match as whole words to avoid false negatives on real secrets
_ALLOWLIST_VALUES = {
    "changeit", "testpassword", "password123", "placeholder",
    "your-password-here", "your_password", "mypassword", "secret123",
    "dummy", "fake", "sample", "replace_me", "your-token-here",
}


def _is_allowlisted(line: str) -> bool:
    """Return True if the line contains a known safe placeholder value as a whole word."""
    lower = line.lower()
    return any(re.search(r'\b' + re.escape(v) + r'\b', lower) for v in _ALLOWLIST_VALUES)


_compiled = None
_compiled_config_mtime = None


def _get_patterns():
    """Get compiled patterns including custom ones from config. Recomputes if config changes."""
    global _compiled, _compiled_config_mtime
    config_path = Path(__file__).parent.parent / "config.yml"
    current_mtime = config_path.stat().st_mtime if config_path.exists() else None

    if _compiled is not None and _compiled_config_mtime == current_mtime:
        return _compiled

    patterns = list(_DEFAULT_PATTERNS)

    config = _load_config()
    custom = config.get("security", {}).get("secret_patterns", [])
    for p in custom:
        if isinstance(p, dict):
            patterns.append((p.get("name", "Custom"), p["regex"], p.get("desc", "")))
        elif isinstance(p, str):
            patterns.append(("Custom", p, "Custom pattern"))

    _compiled = [(name, re.compile(regex), desc) for name, regex, desc in patterns]
    _compiled_config_mtime = current_mtime
    return _compiled


def scan_file(file_path: str) -> List[Finding]:
    """Scan a single file for secrets."""
    findings = []
    path = Path(file_path)

    if not path.exists() or not path.is_file():
        return findings

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    patterns = _get_patterns()

    for line_num, line in enumerate(content.splitlines(), 1):
        for name, regex, _ in patterns:
            if regex.search(line) and not _is_allowlisted(line):
                snippet = line.strip()
                if len(snippet) > 80:
                    snippet = snippet[:80] + "..."
                snippet = regex.sub("[REDACTED]", snippet)
                findings.append(Finding(
                    file=str(file_path),
                    line_num=line_num,
                    pattern_name=name,
                    snippet=snippet,
                ))

    return findings


def scan_staged_files() -> List[Finding]:
    """Scan all git staged files for secrets."""
    exit_code, stdout, _ = safe_run(["git", "diff", "--cached", "--name-only"])
    if exit_code != 0 or not stdout:
        return []
    findings = []
    for file_path in stdout.splitlines():
        file_path = file_path.strip()
        if file_path:
            findings.extend(scan_file(file_path))
    return findings


def scan_directory(dir_path: str) -> List[Finding]:
    """Scan all files in a directory recursively."""
    findings = []
    path = Path(dir_path)
    if not path.exists():
        return findings

    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    skip_exts = {".pyc", ".class", ".jar", ".exe", ".dll", ".so", ".png", ".jpg", ".gif"}

    for file_path in path.rglob("*"):
        if file_path.is_file():
            if any(part in skip_dirs for part in file_path.parts):
                continue
            if file_path.suffix in skip_exts:
                continue
            findings.extend(scan_file(str(file_path)))

    return findings


def main():
    config = _load_config()
    if config.get("disable_secret_scan", False):
        print("Secret scanning disabled in config.")
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Scan for leaked secrets")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="Scan git staged files")
    group.add_argument("--path", help="Scan directory")
    group.add_argument("--file", help="Scan single file")

    args = parser.parse_args()

    if args.staged:
        findings = scan_staged_files()
    elif args.path:
        findings = scan_directory(args.path)
    else:
        findings = scan_file(args.file)

    if findings:
        print(f"\nSECRET SCAN FAILED: {len(findings)} potential secret(s) found\n")
        for f in findings:
            print(f"  {f.file}:{f.line_num} [{f.pattern_name}]")
            print(f"    {f.snippet}\n")
        sys.exit(1)
    else:
        print("Secret scan passed: no secrets detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
