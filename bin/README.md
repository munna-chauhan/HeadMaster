# bin/ — HeadMaster portable interpreter shims

Makes `python`, `python3`, and `py` resolve to whatever Python is installed
on the host (in that probe order). Skill markdown, script shebangs, and
agent prompts can all use a single name without worrying about which one
the user has.

## How it works

1. `.claude/settings.json` prepends `${CLAUDE_PROJECT_DIR}/bin` to `PATH`
   for every Bash invocation and hook.
2. When something runs `python …`, the shell finds `bin/python` first.
3. `bin/python` execs `.claude/hooks/pyrun.sh` (Unix) or
   `bin/python.cmd` invokes `node .claude/hooks/pyrun.js` (Windows).
4. The resolver strips `bin/` from `PATH` and probes `python3 → python → py`
   until it finds a real interpreter.

## Files

| File              | Platform | Delegates to                  |
| ----------------- | -------- | ----------------------------- |
| `python`          | Unix     | `.claude/hooks/pyrun.sh`      |
| `python3`         | Unix     | `.claude/hooks/pyrun.sh`      |
| `py`              | Unix     | `.claude/hooks/pyrun.sh`      |
| `python.cmd`      | Windows  | `.claude/hooks/pyrun.js`      |
| `python3.cmd`     | Windows  | `.claude/hooks/pyrun.js`      |
| `py.cmd`          | Windows  | `.claude/hooks/pyrun.js`      |

## When PATH isn't set

If `bin/` isn't on `PATH` (e.g. running scripts outside Claude Code),
`activate.py` emits a warning at SessionStart with a one-line fix.
