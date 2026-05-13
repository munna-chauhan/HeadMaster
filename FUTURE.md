# HeadMaster — Future Scope

Captured items deferred from PLAN.md. Not in PR1–PR9. Revisit when Phase 1 individual-developer rollout is stable.

---

## Phase 2 — Team Mode

Each item below is a discrete future feature. None depend on each other unless noted.

| Mechanism | What it means | Where it lives |
|---|---|---|
| Shared agent memory | `memory/agents/{agent}/MEMORY.md` committed to a `headmaster-team-memory` repo (or team repo subdir), pulled at session start. Per-machine entries route to `memory/agents/{agent}/MEMORY.local.md`. | New `memory-shared/` dir, new hook `activate.py` step |
| Project-level memory | `memory/projects/{project}/` (repo registry, style profile, recurring patterns) committed alongside the project repo, not in HeadMaster. | New `projects.{slug}.memory_path` config key |
| Shared config baseline | Split `config.yml` → `config.yml` (shared, committed) + `config.local.yml` (per-dev overrides for `projects.active`, paths, `jira_push`). `ConfigResolver` merges them. | `scripts/config_utils.py` change |
| Portable `.mcp.json` | Drop `cmd /c` shape. Platform detection writes the right form on first run. | `.mcp.json`, new `scripts/setup_mcp.py` |
| Onboarding script | `scripts/onboard.py` copies `.example` files, validates `node`/`python`, prompts for env vars, runs `setup-env`. | New script |
| Per-stack permission profiles | `settings.json` split into a JVM profile, a JS profile, a polyglot profile. User picks one during onboard. | New `.claude/profiles/` dir |
| Feature-slug collision handling | Same slug taken by another dev on the same project → `init-feature` warns, offers a suffix. | `init-feature` SKILL change |
| Team telemetry sink | `monitoring.skill_tracking.*` keys (currently dead) wired to a real consumer that writes `memory/team-metrics.jsonl`, optionally pushed to a shared dashboard. | `run_logger.py` + new sink |
| Non-Claude AI agent support | Add `AGENTS.md` at repo root (tool-agnostic subset of CLAUDE.md rules) when Cursor/Aider/Copilot/Codex use becomes a real need. | New `AGENTS.md` |

---

## Phase 3 — Enterprise (captured-only)

SSO/RBAC per project, centralized telemetry dashboard, SBOM/IaC scanning, audit-trail export, multi-region.

---

## Deferred from Audit §10

Items from the original 10-point audit explicitly out of scope for PR1–PR9:

| Item | Reason deferred |
|---|---|
| Versioning of agents/skills (audit §10 item 16) | Defer until Phase 2 needs it |
| Token-budget enforcement at runtime | Replaced by CLAUDE.md token-efficiency guidance |
| Team enablement gaps (audit §8) | All captured in Phase 2 above |
