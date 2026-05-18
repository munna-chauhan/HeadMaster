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
"""Audit agent + skill counts against README.md and CLAUDE.md.

Usage:
  sh scripts/audit_inventory.py          # check only, exit 1 on drift
  sh scripts/audit_inventory.py --fix    # update counts in-place, exit 0

Checks:
  - .claude/agents/*.md  (excludes references/ subdir)
  - .claude/skills/*/SKILL.md
  Counts must match every occurrence of "N agents" and "N skills" in
  README.md and .claude/CLAUDE.md.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
README     = REPO_ROOT / "README.md"
CLAUDE_MD  = REPO_ROOT / ".claude" / "CLAUDE.md"

TARGET_FILES = [README, CLAUDE_MD]


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
    print(f"audit_inventory: agents={count_agents()}, skills={count_skills()}")

    errors = audit(fix)

    if errors:
        for e in errors:
            print(f"  DRIFT: {e}")
        sys.exit(1)

    print("  ok: counts match")
    sys.exit(0)


if __name__ == "__main__":
    main()
