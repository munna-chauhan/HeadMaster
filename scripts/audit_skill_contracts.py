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
"""
audit_skill_contracts.py — Detect SKILL.md command references not implemented in scripts.

For each .claude/skills/*/SKILL.md, finds `sh <path>.py <action>` in bash blocks
and verifies each action appears in the referenced script's argparse choices.

Usage:
  sh scripts/audit_skill_contracts.py

Exit 0: clean. Exit 1: drift found.
"""
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Capture positional subcommand: starts with a letter (not a -- flag)
_CMD = re.compile(r'\bsh\s+([\w./\-]+\.py)\s+([a-zA-Z][a-zA-Z0-9_\-]*)')


def _implemented_commands(path: Path) -> set:
    """Extract valid subcommand names from a Python script via AST.

    Detects both argparse `choices=[...]` and sys.argv dispatch
    patterns like `if cmd == "name"` or `cmd in ("a", "b")`.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return set()

    found: set = set()

    for node in ast.walk(tree):
        # argparse: add_argument("action", choices=["cmd1", "cmd2"])
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "choices" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    for elt in kw.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            found.add(elt.value)
            # argparse subparsers: subparsers.add_parser("cmd")
            func = getattr(node, "func", None)
            if func and getattr(func, "attr", None) == "add_parser":
                if node.args and isinstance(node.args[0], ast.Constant):
                    found.add(node.args[0].value)

        # sys.argv dispatch: if cmd == "name" / elif cmd == "name"
        # Also: cmd in ("a", "b") or cmd in ["a", "b"]
        if isinstance(node, ast.Compare):
            ops = node.ops
            comps = node.comparators
            # cmd == "name"
            if len(ops) == 1 and isinstance(ops[0], ast.Eq):
                for side in (node.left, comps[0]):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str):
                        found.add(side.value)
            # cmd in ("a", "b")
            if len(ops) == 1 and isinstance(ops[0], ast.In):
                container = comps[0]
                if isinstance(container, (ast.Tuple, ast.List)):
                    for elt in container.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            found.add(elt.value)

    return found


def _skill_commands(skill_md: Path) -> list:
    """Return [(script_rel, action), ...] from bash blocks in SKILL.md."""
    text = skill_md.read_text(encoding="utf-8")
    results = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            for m in _CMD.finditer(line):
                results.append((m.group(1), m.group(2)))
    return results


def audit(repo_root: Path = REPO_ROOT) -> list:
    """Return list of {skill, script, missing, error?} dicts."""
    findings = []
    skills_dir = repo_root / ".claude" / "skills"
    if not skills_dir.exists():
        return findings
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        by_script: dict = {}
        for script_rel, action in _skill_commands(skill_md):
            by_script.setdefault(script_rel, set()).add(action)
        for script_rel, actions in by_script.items():
            script_path = repo_root / script_rel
            if not script_path.exists():
                findings.append({
                    "skill": skill_md.parent.name,
                    "script": script_rel,
                    "missing": sorted(actions),
                    "error": "script not found",
                })
                continue
            missing = sorted(actions - _implemented_commands(script_path))
            if missing:
                findings.append({
                    "skill": skill_md.parent.name,
                    "script": script_rel,
                    "missing": missing,
                })
    return findings


def main():
    findings = audit()
    if not findings:
        print("[OK] No skill contract drift")
        sys.exit(0)
    for f in findings:
        note = f" ({f['error']})" if "error" in f else ""
        print(f"[DRIFT] {f['skill']}: {f['script']}{note} — missing: {', '.join(f['missing'])}")
    sys.exit(1)


if __name__ == "__main__":
    main()
