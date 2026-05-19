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
"""Tests for audit_skill_contracts.py."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_skill_contracts import audit, _implemented_commands, _skill_commands

_SCRIPT_PREPROCESS_ONLY = (
    'import argparse\n'
    'p = argparse.ArgumentParser()\n'
    'p.add_argument("action", choices=["preprocess"])\n'
)

_SCRIPT_MULTI_ACTION = (
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


def test_no_drift():
    root = _repo(
        {"my-skill": "```bash\nsh scripts/tool.py preprocess input.md\n```"},
        {"scripts/tool.py": _SCRIPT_PREPROCESS_ONLY},
    )
    assert audit(root) == []
    print("[PASS] no drift when commands match")


def test_drift_detected():
    md = "```bash\nsh scripts/tool.py preprocess x\nsh scripts/tool.py update 1 f.xml T\nsh scripts/tool.py create T f.xml 2\n```"
    root = _repo({"my-skill": md}, {"scripts/tool.py": _SCRIPT_PREPROCESS_ONLY})
    findings = audit(root)
    assert len(findings) == 1
    assert set(findings[0]["missing"]) == {"update", "create"}
    print("[PASS] drift detected: update, create")


def test_missing_script():
    root = _repo({"my-skill": "```bash\nsh scripts/ghost.py foo\n```"}, {})
    findings = audit(root)
    assert len(findings) == 1 and "error" in findings[0]
    print("[PASS] missing script reported as error")


def test_all_actions_implemented():
    md = "```bash\nsh scripts/tool.py preprocess x\nsh scripts/tool.py update 1 f T\nsh scripts/tool.py create T f 2\n```"
    root = _repo({"my-skill": md}, {"scripts/tool.py": _SCRIPT_MULTI_ACTION})
    assert audit(root) == []
    print("[PASS] no drift when all actions implemented")


def test_empty_skills_dir():
    assert audit(_repo({}, {})) == []
    print("[PASS] empty skills dir: no findings")


def test_no_bash_blocks():
    root = _repo({"my-skill": "# No bash blocks here\nJust prose.\n"}, {})
    assert audit(root) == []
    print("[PASS] SKILL.md with no bash blocks: no findings")


def test_argparse_choices_extracted():
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "tool.py"
    p.write_text('import argparse\np=argparse.ArgumentParser()\np.add_argument("a",choices=["x","y"])\n')
    assert _implemented_commands(p) == {"x", "y"}
    print("[PASS] argparse choices extracted correctly")


def test_argparse_choices_bad_file():
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "bad.py"
    p.write_text("def (broken syntax:", encoding="utf-8")
    assert _implemented_commands(p) == set()
    print("[PASS] invalid file returns empty choices")


def test_sysargv_dispatch_detected():
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "tool.py"
    p.write_text('import sys\ncmd=sys.argv[1]\nif cmd == "reopen": pass\nelif cmd == "close": pass\n')
    cmds = _implemented_commands(p)
    assert "reopen" in cmds and "close" in cmds
    print("[PASS] sys.argv dispatch commands detected")


def test_flag_args_not_captured():
    md = "```bash\nsh scripts/tool.py --all\nsh scripts/tool.py preprocess x\n```"
    root = _repo({"s": md}, {"scripts/tool.py": _SCRIPT_PREPROCESS_ONLY})
    # --all should not be captured as a subcommand (starts with -)
    cmds = _skill_commands(root / ".claude" / "skills" / "s" / "SKILL.md")
    names = [c[1] for c in cmds]
    assert "preprocess" in names and "--all" not in names
    print("[PASS] -- flags not captured as subcommands")


def test_skill_commands_outside_bash_blocks_ignored():
    md = "Not in block: sh scripts/tool.py hidden\n```bash\nsh scripts/tool.py visible\n```"
    root = _repo({"s": md}, {"scripts/tool.py": _SCRIPT_PREPROCESS_ONLY})
    cmds = _skill_commands(root / ".claude" / "skills" / "s" / "SKILL.md")
    assert len(cmds) == 1 and cmds[0][1] == "visible"
    print("[PASS] commands outside bash blocks are ignored")


if __name__ == "__main__":
    test_no_drift()
    test_drift_detected()
    test_missing_script()
    test_all_actions_implemented()
    test_empty_skills_dir()
    test_no_bash_blocks()
    test_argparse_choices_extracted()
    test_argparse_choices_bad_file()
    test_skill_commands_outside_bash_blocks_ignored()
    print("\n[PASS] All audit_skill_contracts tests passed")
