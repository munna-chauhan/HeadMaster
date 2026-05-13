#!/usr/bin/env python
"""Extract style/lint rules from a repo root into a compact markdown table.

Discovery-driven: scans for known config file patterns, parses generically by
format (ini, json, yaml, toml, xml, key=value). No tool names hardcoded.

Usage:
  python scripts/style_extractor.py <repo-path> [--output <path>]

Output:
  Markdown table  Rule | Value | Source  capped at 50 rules.

Exit codes:
  0  rules found and written
  1  no style configs found
  2  error
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

RULE_CAP = 50

# ---------------------------------------------------------------------------
# Generic format parsers — yield (rule, value, source)
# ---------------------------------------------------------------------------

def _parse_ini_kv(path: Path) -> Iterator[tuple[str, str, str]]:
    """INI / editorconfig: section-aware key=value."""
    section = "*"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line[0] in ("#", ";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            yield key.strip(), val.strip(), f"{path.name}[{section}]"


def _parse_kv(path: Path) -> Iterator[tuple[str, str, str]]:
    """Plain key=value or key: value, skip comments."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line[0] in ("#", "//", ";"):
            continue
        for sep in ("=", ":"):
            if sep in line:
                key, _, val = line.partition(sep)
                yield key.strip(), val.strip(), path.name
                break


def _parse_json(path: Path) -> Iterator[tuple[str, str, str]]:
    """JSON: emit all scalar leaf values at depth ≤ 2."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    for k, v in data.items():
        if isinstance(v, (str, int, float, bool)):
            yield k, str(v), path.name
        elif isinstance(v, dict):
            for sk, sv in v.items():
                if isinstance(sv, (str, int, float, bool)):
                    yield f"{k}.{sk}", str(sv), path.name
        elif isinstance(v, list) and v and isinstance(v[0], (str, int)):
            # e.g. eslint rule ["error", {opts}] → emit severity
            yield k, str(v[0]), path.name


def _parse_yaml(path: Path) -> Iterator[tuple[str, str, str]]:
    """YAML: same depth-≤-2 scalar walk as JSON parser."""
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    for k, v in data.items():
        if isinstance(v, (str, int, float, bool)):
            yield k, str(v), path.name
        elif isinstance(v, dict):
            for sk, sv in v.items():
                if isinstance(sv, (str, int, float, bool)):
                    yield f"{k}.{sk}", str(sv), path.name
        elif isinstance(v, list) and v and isinstance(v[0], (str, int)):
            yield k, str(v[0]), path.name


def _parse_toml(path: Path) -> Iterator[tuple[str, str, str]]:
    """TOML: emit scalar values; for [tool.*] sections prefix with tool name."""
    try:
        import tomllib  # type: ignore
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    # Top-level scalars
    for k, v in data.items():
        if isinstance(v, (str, int, float, bool)):
            yield k, str(v), path.name
    # [tool.*] sections — read ALL, whatever tools are present
    for tool_name, cfg in data.get("tool", {}).items():
        if not isinstance(cfg, dict):
            continue
        for k, v in cfg.items():
            if isinstance(v, (str, int, float, bool)):
                yield f"tool.{tool_name}.{k}", str(v), f"{path.name}[tool.{tool_name}]"


def _parse_xml_properties(path: Path) -> Iterator[tuple[str, str, str]]:
    """XML: extract name/value attribute pairs from any element."""
    try:
        tree = ET.parse(path)
    except Exception:
        return
    for elem in tree.iter():
        name = elem.get("name") or elem.get("id") or elem.tag
        value = elem.get("value") or elem.get("enabled") or elem.text
        if name and value and value.strip():
            parent = elem.get("name", elem.tag)
            yield name, value.strip(), f"{path.name}<{elem.tag}>"


# ---------------------------------------------------------------------------
# Discovery: find style/lint configs at repo root — format detected by pattern
# ---------------------------------------------------------------------------

# (glob_pattern, format)  — searched at repo root only (not recursive)
_CONFIG_PATTERNS: list[tuple[str, str]] = [
    (".editorconfig",   "ini"),
    (".*rc",            "json"),     # .eslintrc, .babelrc, .stylelintrc ...
    (".*rc.json",       "json"),
    (".*rc.yaml",       "yaml"),
    (".*rc.yml",        "yaml"),
    (".*rc.toml",       "toml"),
    ("*fmt.toml",       "toml"),     # rustfmt.toml, .rustfmt.toml
    (".rustfmt.toml",   "toml"),
    ("*fmt.conf",       "kv"),       # .scalafmt.conf
    ("*.scalafmt.conf", "kv"),
    (".scalafmt.conf",  "kv"),
    ("pyproject.toml",  "toml"),
    ("*.xml",           "xml"),      # checkstyle.xml, spotbugs.xml ...
]


def find_style_configs(repo: Path) -> list[tuple[Path, str]]:
    """Return (path, format) for all style configs discovered at repo root."""
    seen: set[Path] = set()
    found: list[tuple[Path, str]] = []

    def _add(p: Path, fmt: str) -> None:
        if p not in seen and p.exists() and p.is_file():
            seen.add(p)
            found.append((p, fmt))

    for pattern, fmt in _CONFIG_PATTERNS:
        for p in repo.glob(pattern):
            # Skip lock files, dist artefacts, large generated files
            if any(x in p.name for x in ("lock", "dist", "generated")):
                continue
            _add(p, fmt)

    # Validate: try to parse JSON-detected files; fall back to kv if not valid JSON
    result: list[tuple[Path, str]] = []
    for path, fmt in found:
        if fmt == "json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
                result.append((path, "json"))
            except Exception:
                result.append((path, "kv"))
        else:
            result.append((path, fmt))

    return result


# ---------------------------------------------------------------------------
# Format dispatch
# ---------------------------------------------------------------------------

_PARSERS = {
    "ini":  _parse_ini_kv,
    "kv":   _parse_kv,
    "json": _parse_json,
    "yaml": _parse_yaml,
    "toml": _parse_toml,
    "xml":  _parse_xml_properties,
}


def extract_rules(repo: Path) -> list[tuple[str, str, str]]:
    configs = find_style_configs(repo)
    rules: list[tuple[str, str, str]] = []
    for path, fmt in configs:
        parser = _PARSERS.get(fmt)
        if not parser:
            continue
        for triple in parser(path):
            rules.append(triple)
            if len(rules) >= RULE_CAP:
                return rules
    return rules


def render_markdown(repo_name: str, rules: list[tuple[str, str, str]]) -> str:
    lines = [
        f"# Style Rules — {repo_name}",
        "",
        "| Rule | Value | Source |",
        "|------|-------|--------|",
    ]
    for rule, value, source in rules:
        lines.append(f"| `{rule}` | `{value}` | {source} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_path")
    ap.add_argument("--output", "-o")
    args = ap.parse_args()

    repo = Path(args.repo_path).resolve()
    if not repo.is_dir():
        print(f"ERROR: not a directory: {repo}", file=sys.stderr)
        sys.exit(2)

    rules = extract_rules(repo)
    if not rules:
        sys.exit(1)

    md = render_markdown(repo.name, rules)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"Style rules: {out} ({len(rules)} rules)")
    else:
        print(md)


if __name__ == "__main__":
    main()
