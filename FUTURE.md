# HeadMaster — Future Scope

Items deferred from the current single-developer rollout. Not on any active milestone. Revisit once Phase 1 is stable for a senior developer working solo.

---

## Phase 2 — Role Split (architect vs developer)

Goal: keep `plan` and `design` as an architect-owned upstream, and let one or more developers pick up `breakdown` and `execute` from the approved TDD onward.

| Item | What it means | Where it lives |
|---|---|---|
| Stage handoff contract | Approved TDD + `loop_state.json` snapshot is the only artifact crossing the architect → developer boundary. Architect machine can ship this bundle without sharing memory or config. | `scripts/state_manager.py`, new export/import commands |
| Per-stage independence | Each skill (`/plan`, `/design`, `/breakdown`, `/execute`) runs given its required upstream artifact alone — no implicit dependency on prior session state beyond `loop_state.json` and the named artifact. | Audit + minor edits in skill stage files |
| Shared agent memory baseline | `memory/agents/{agent}/MEMORY.md` reviewed and committable per team; per-machine entries route to `MEMORY.local.md`. | `activate.py` reads both; `update_agent_memory.py` writes the right file |
| Shared config baseline | Split `config.yml` → shared committed file + `config.local.yml` overlay (per-dev: `projects.active`, paths, `jira_push`). `ConfigResolver` merges them. | `scripts/config_utils.py` |
| Onboarding script | `scripts/onboard.py` validates `node`/`python`, prompts for env vars, copies `.example` files, runs `setup_projects.py` and `setup-env`. | New script |
| Slug collision handling | Same feature slug taken by another dev on the same project → `init-feature` warns, offers a suffix. | `init-feature` SKILL |
| Per-stack permission profiles | `.claude/settings.json` split into JVM / JS / polyglot profiles; user picks one during onboard. | `.claude/profiles/` |
| Project-level memory | `memory/projects/{project}/` (repo registry, style profile, recurring patterns) committed alongside the project repo, not in HeadMaster. | New `projects.{slug}.memory_path` config key |
| Portable `.mcp.json` | Drop `cmd /c` shape. Platform detection writes the right form on first run. | `.mcp.json`, new `scripts/setup_mcp.py` |
| Team telemetry sink | `monitoring.skill_tracking.*` keys (currently dead) wired to a real consumer that writes `memory/team-metrics.jsonl`, optionally pushed to a shared dashboard. | `run_logger.py` + new sink |
| Non-Claude AI agent support | Add `AGENTS.md` at repo root (tool-agnostic subset of CLAUDE.md rules) when Cursor/Aider/Copilot/Codex use becomes a real need. | New `AGENTS.md` |

---

## Phase 3 — Enterprise (captured-only)

SSO/RBAC per project, centralized telemetry dashboard, SBOM/IaC scanning, audit-trail export, multi-region.

---

## Deferred capability items

| Item | Reason deferred |
|---|---|
| Versioning of agents/skills | Defer until memory entries need to target a specific version |
| Memory-entry quality signal | No hit/miss tracking on stored patterns today; deduplication is the only quality control |
| AST / embedding-based codebase understanding | Current keyword + 2-file-read heuristic is sufficient for known patterns |
| Native mobile build-marker detection (Xcode, SwiftPM) | Add when first iOS feature lands |
| Token-budget enforcement at runtime | Replaced by CLAUDE.md token-efficiency guidance |
