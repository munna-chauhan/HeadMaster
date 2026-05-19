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
"""Tests for audit_inventory.py — contract audit and count audit."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from audit_inventory import audit_contracts, _implemented_commands, _skill_commands, count_agents, count_skills, audit

_CHOICES_ONE = (
    'import argparse\n'
    'p = argparse.ArgumentParser()\n'
    'p.add_argument("action", choices=["preprocess"])\n'
)
_CHOICES_THREE = (
    'import argparse\n'
    'p = argparse.ArgumentParser()\n'
    'p.add_argument("action", choices=["preprocess", "update", "create"])\n'
)


def _repo(skills: dict, scripts: dict) -> Path:
    tmp = Path(tempfile.mkdtemp())
    for name, content in skills.items():
        d = tmp / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(content, encoding="utf-8")
    for rel, content in scripts.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


# ---------------------------------------------------------------------------
# Contract audit
# ---------------------------------------------------------------------------

def test_no_drift():
    root = _repo(
        {"my-skill": "```bash\nsh scripts/tool.py preprocess input.md\n```"},
        {"scripts/tool.py": _CHOICES_ONE},
    )
    assert audit_contracts(root) == []


def test_drift_detected():
    md = "```bash\nsh scripts/tool.py preprocess x\nsh scripts/tool.py update 1 f.xml T\nsh scripts/tool.py create T f.xml 2\n```"
    root = _repo({"my-skill": md}, {"scripts/tool.py": _CHOICES_ONE})
    findings = audit_contracts(root)
    assert len(findings) == 1
    assert set(findings[0]["missing"]) == {"update", "create"}


def test_missing_script():
    root = _repo({"my-skill": "```bash\nsh scripts/ghost.py foo\n```"}, {})
    findings = audit_contracts(root)
    assert len(findings) == 1 and "error" in findings[0]


def test_all_actions_implemented():
    md = "```bash\nsh scripts/tool.py preprocess x\nsh scripts/tool.py update 1 f T\nsh scripts/tool.py create T f 2\n```"
    root = _repo({"my-skill": md}, {"scripts/tool.py": _CHOICES_THREE})
    assert audit_contracts(root) == []


def test_empty_skills_dir():
    assert audit_contracts(_repo({}, {})) == []


def test_no_bash_blocks():
    root = _repo({"my-skill": "# No bash blocks here\nJust prose.\n"}, {})
    assert audit_contracts(root) == []


def test_argparse_choices_extracted():
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "tool.py"
    p.write_text('import argparse\np=argparse.ArgumentParser()\np.add_argument("a",choices=["x","y"])\n')
    assert _implemented_commands(p) == {"x", "y"}


def test_argparse_choices_bad_file():
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "bad.py"
    p.write_text("def (broken syntax:", encoding="utf-8")
    assert _implemented_commands(p) == set()


def test_sysargv_dispatch_detected():
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "tool.py"
    p.write_text('import sys\ncmd=sys.argv[1]\nif cmd == "reopen": pass\nelif cmd == "close": pass\n')
    cmds = _implemented_commands(p)
    assert "reopen" in cmds and "close" in cmds


def test_flag_args_not_captured():
    md = "```bash\nsh scripts/tool.py --all\nsh scripts/tool.py preprocess x\n```"
    root = _repo({"s": md}, {"scripts/tool.py": _CHOICES_ONE})
    cmds = _skill_commands(root / ".claude" / "skills" / "s" / "SKILL.md")
    names = [c[1] for c in cmds]
    assert "preprocess" in names and "--all" not in names


def test_skill_commands_outside_bash_blocks_ignored():
    md = "Not in block: sh scripts/tool.py hidden\n```bash\nsh scripts/tool.py visible\n```"
    root = _repo({"s": md}, {"scripts/tool.py": _CHOICES_ONE})
    cmds = _skill_commands(root / ".claude" / "skills" / "s" / "SKILL.md")
    assert len(cmds) == 1 and cmds[0][1] == "visible"


# ---------------------------------------------------------------------------
# Count audit
# ---------------------------------------------------------------------------

def _count_repo(agents: list[str], skills: list[str]) -> Path:
    tmp = Path(tempfile.mkdtemp())
    agents_dir = tmp / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    skills_dir = tmp / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    for a in agents:
        (agents_dir / f"{a}.md").write_text(f"# {a}\n", encoding="utf-8")
    for s in skills:
        d = skills_dir / s
        d.mkdir()
        (d / "SKILL.md").write_text(f"# {s}\n", encoding="utf-8")
    return tmp


def test_count_agents(monkeypatch):
    tmp = _count_repo(["alpha", "beta", "gamma"], [])
    monkeypatch.setattr("audit_inventory.AGENTS_DIR", tmp / ".claude" / "agents")
    monkeypatch.setattr("audit_inventory.SKILLS_DIR", tmp / ".claude" / "skills")
    assert count_agents() == 3


def test_count_skills(monkeypatch):
    tmp = _count_repo([], ["plan", "design", "execute"])
    monkeypatch.setattr("audit_inventory.AGENTS_DIR", tmp / ".claude" / "agents")
    monkeypatch.setattr("audit_inventory.SKILLS_DIR", tmp / ".claude" / "skills")
    assert count_skills() == 3


def test_count_audit_pass(monkeypatch):
    tmp = _count_repo(["a", "b"], ["s1", "s2"])
    monkeypatch.setattr("audit_inventory.AGENTS_DIR", tmp / ".claude" / "agents")
    monkeypatch.setattr("audit_inventory.SKILLS_DIR", tmp / ".claude" / "skills")
    readme = tmp / "README.md"
    readme.write_text("2 agents and 2 skills available.\n", encoding="utf-8")
    monkeypatch.setattr("audit_inventory.TARGET_FILES", [readme])
    errors = audit(fix=False)
    assert errors == []


def test_count_audit_drift_detected(monkeypatch):
    tmp = _count_repo(["a", "b", "c"], ["s1"])
    monkeypatch.setattr("audit_inventory.AGENTS_DIR", tmp / ".claude" / "agents")
    monkeypatch.setattr("audit_inventory.SKILLS_DIR", tmp / ".claude" / "skills")
    monkeypatch.setattr("audit_inventory.REPO_ROOT", tmp)
    readme = tmp / "README.md"
    readme.write_text("1 agent and 1 skill available.\n", encoding="utf-8")
    monkeypatch.setattr("audit_inventory.TARGET_FILES", [readme])
    errors = audit(fix=False)
    assert any("agent" in e for e in errors)


def test_count_audit_fix(monkeypatch):
    tmp = _count_repo(["a", "b"], ["s1", "s2", "s3"])
    monkeypatch.setattr("audit_inventory.AGENTS_DIR", tmp / ".claude" / "agents")
    monkeypatch.setattr("audit_inventory.SKILLS_DIR", tmp / ".claude" / "skills")
    monkeypatch.setattr("audit_inventory.REPO_ROOT", tmp)
    readme = tmp / "README.md"
    readme.write_text("99 agents and 99 skills available.\n", encoding="utf-8")
    monkeypatch.setattr("audit_inventory.TARGET_FILES", [readme])
    audit(fix=True)
    updated = readme.read_text(encoding="utf-8")
    assert "2 agents" in updated and "3 skills" in updated
