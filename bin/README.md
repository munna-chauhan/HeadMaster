# bin/ — HeadMaster portable interpreter shim

Single canonical name: `python`. Everywhere inside HeadMaster (skills,
scripts, hooks, agent prompts, shebangs) calls `python`. The shim resolves
to whatever interpreter the host actually has — `python3`, `py3`, `python`,
or `py` — and caches the result in `.claude/cache/python-interpreter`
(gitignored). Subsequent invocations exec the cached path directly.

## How it works

1. `.claude/settings.json` prepends `${CLAUDE_PROJECT_DIR}/bin` to `PATH`
   for every Bash invocation and hook.
2. When something runs `python …`, the shell finds `bin/python` first.
3. `bin/python` execs `.claude/hooks/pyrun.sh` (Unix) or
   `bin/python.cmd` invokes `node .claude/hooks/pyrun.js` (Windows).
4. The resolver checks `.claude/cache/python-interpreter`. On hit + still
   executable → exec the cached path. On miss/stale → probe
   `python3 → py3 → python → py`, write the resolved path to the cache,
   then exec.

## Files

| File          | Platform | Delegates to                  |
| ------------- | -------- | ----------------------------- |
| `python`      | Unix     | `.claude/hooks/pyrun.sh`      |
| `python.cmd`  | Windows  | `.claude/hooks/pyrun.js`      |

## Cache

`.claude/cache/python-interpreter` holds the absolute path of the resolved
interpreter (one line). Delete it to force a re-probe after installing or
uninstalling a Python version. The file is gitignored — host-specific.

## When PATH isn't set

If `bin/` isn't on `PATH` (e.g. running scripts outside Claude Code),
`activate.py` emits a warning at SessionStart with a one-line fix.
