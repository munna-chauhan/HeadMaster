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
"""Audit HeadMaster inventory: agent/skill counts and SKILL.md contract drift.

Usage:
  sh scripts/audit_inventory.py          # check counts + contracts, exit 1 on drift
  sh scripts/audit_inventory.py --fix    # auto-fix counts (contracts drift reported only)

Checks:
  1. Agent/skill counts match README.md and .claude/CLAUDE.md
  2. Every command referenced in SKILL.md bash blocks exists in the script's argparse
"""
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
README     = REPO_ROOT / "README.md"
CLAUDE_MD  = REPO_ROOT / ".claude" / "CLAUDE.md"

TARGET_FILES = [README, CLAUDE_MD]


# ---------------------------------------------------------------------------
# Contract audit (SKILL.md vs script implementations)
# ---------------------------------------------------------------------------

# Positional subcommand after `sh <path>.py` — must start with a letter
_CMD = re.compile(r'\bsh\s+([\w./\-]+\.py)\s+([a-zA-Z][a-zA-Z0-9_\-]*)')


def _implemented_commands(path: Path) -> set:
    """Return subcommand names implemented in a script via argparse or sys.argv dispatch."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    found: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "choices" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    for elt in kw.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            found.add(elt.value)
            func = getattr(node, "func", None)
            if func and getattr(func, "attr", None) == "add_parser":
                if node.args and isinstance(node.args[0], ast.Constant):
                    found.add(node.args[0].value)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            if isinstance(node.ops[0], ast.Eq):
                for side in (node.left, node.comparators[0]):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str):
                        found.add(side.value)
            if isinstance(node.ops[0], ast.In):
                container = node.comparators[0]
                if isinstance(container, (ast.Tuple, ast.List)):
                    for elt in container.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            found.add(elt.value)
    return found


def _skill_commands(skill_md: Path) -> list:
    """Return [(script_rel, action), ...] from bash blocks in a SKILL.md."""
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


def audit_contracts(repo_root: Path) -> list:
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
                findings.append({"skill": skill_md.parent.name, "script": script_rel,
                                  "missing": sorted(actions), "error": "script not found"})
                continue
            missing = sorted(actions - _implemented_commands(script_path))
            if missing:
                findings.append({"skill": skill_md.parent.name, "script": script_rel,
                                  "missing": missing})
    return findings


# ---------------------------------------------------------------------------
# Count audit (agents + skills)
# ---------------------------------------------------------------------------

def count_agents() -> int:
    return len([
        f for f in AGENTS_DIR.glob("*.md")
        if f.is_file() and f.parent == AGENTS_DIR
    ])


def count_skills() -> int:
    return len([
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    ])


def audit(fix: bool) -> list[str]:
    agent_count = count_agents()
    skill_count = count_skills()
    errors = []

    for path in TARGET_FILES:
        if not path.exists():
            errors.append(f"MISSING: {path}")
            continue

        text = path.read_text(encoding="utf-8")
        updated = text

        # Match badge alt text and inline counts: e.g. "12 agents", "12 Agents"
        agent_pattern = re.compile(r'(\d+)(\s+[Aa]gents?)')
        skill_pattern = re.compile(r'(\d+)(\s+[Ss]kills?)')

        agent_mismatches = [
            int(m.group(1)) for m in agent_pattern.finditer(text)
            if int(m.group(1)) != agent_count
        ]
        skill_mismatches = [
            int(m.group(1)) for m in skill_pattern.finditer(text)
            if int(m.group(1)) != skill_count
        ]

        if agent_mismatches:
            if fix:
                updated = agent_pattern.sub(lambda m: f"{agent_count}{m.group(2)}", updated)
            else:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}: agent count(s) {agent_mismatches} "
                    f"!= actual {agent_count}"
                )

        if skill_mismatches:
            if fix:
                updated = skill_pattern.sub(lambda m: f"{skill_count}{m.group(2)}", updated)
            else:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}: skill count(s) {skill_mismatches} "
                    f"!= actual {skill_count}"
                )

        if fix and updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"  fixed: {path.relative_to(REPO_ROOT)}")

    return errors


def main() -> None:
    fix = "--fix" in sys.argv
    failed = False

    # 1. Count check
    print(f"audit_inventory: agents={count_agents()}, skills={count_skills()}")
    count_errors = audit(fix)
    if count_errors:
        for e in count_errors:
            print(f"  DRIFT: {e}")
        failed = True
    else:
        print("  ok: counts match")

    # 2. Contract check
    contract_findings = audit_contracts(REPO_ROOT)
    if contract_findings:
        print("\naudit_contracts:")
        for f in contract_findings:
            note = f" ({f['error']})" if "error" in f else ""
            print(f"  DRIFT: {f['skill']}: {f['script']}{note} — missing: {', '.join(f['missing'])}")
        failed = True
    else:
        print("  ok: skill contracts match")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
