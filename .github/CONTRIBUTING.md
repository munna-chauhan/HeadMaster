# Contributing to HeadMaster

Thanks for the interest. HeadMaster is an open-source ADLC built on Claude Code; the orchestration layer (agents, skills, scripts, hooks) lives in this repo.

## Quick rules

- Open an issue before non-trivial PRs to align on scope.
- Keep PRs focused — one concern per PR.
- Match existing style. `pytest scripts/tests/ -q` must stay green.
- Changes under `.claude/agents/`, `.claude/skills/`, `.claude/workflows/`, `.claude/hooks/`, `.claude/settings.json`, and the listed scripts in `.claude/CLAUDE.md` require explicit human approval before merge — no auto-merge regardless of CI.
- Don't commit secrets, project-specific `config.yml`, or feature artifacts under `docs/features/` and `memory/`.

## Dev setup

```bash
git clone https://github.com/<your-fork>/HeadMaster.git && cd HeadMaster
cp config.yml.example config.yml          # edit projects.active + root
python scripts/setup_projects.py          # writes .claude/settings.local.json
python -m pytest scripts/tests/ -q
```

## Reporting bugs

Use the issue template. Include: HeadMaster commit SHA, Python version, Node version, OS, the failing skill/agent/script, and the full command + error.

## License

By contributing you agree your contributions are licensed under Apache 2.0 (see [LICENSE](../LICENSE)).
