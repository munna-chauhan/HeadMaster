# HeadMaster Improvement Plan

Source: review against the 10-point audit (stale info, config linkage, capabilities, greenfield vs legacy, language independence, project understanding + self-improvement, learnings, multi-dev enrollment, audience, improvements).

This plan converts the audit into a **PR sequence** and an **audience-rollout addition to README**. HeadMaster is built on Claude Code; `.claude/CLAUDE.md` remains the single rule file. Support for non-Claude AI agents (Cursor, Aider, Copilot, Codex, Cody, ChatGPT) is captured as future scope, not built now.

---

## 1. Audience Rollout — to be added to README ("Who Can Use This")

Replaces the current Best Practices section ordering. Two named phases, with a captured-but-deferred Phase 3.

### Phase 1 — Individual Developer (today's state, after PR1–PR3 land)

Target users:
- Solo senior / staff engineer working across one or more existing repos
- Tech leads running design reviews (`/plan`, `/design`, `/review-tdd` standalone)
- Security engineers using `/scan`
- Anyone running HeadMaster on a single workstation

Why it works today:
- `config.yml` is per-machine (gitignored)
- `memory/` is per-machine (gitignored)
- Jira creds via personal env vars
- `setup-env` writes a personal `repo-registry.yml`

Limitations made explicit in the README:
- Agent memory does not cross machines
- Two devs cannot share progress on the same feature slug without manually moving `memory/features/{project}/{slug}/loop_state.json`

### Phase 2 — Team Mode (future scope — captured here, not built in PR1–PR7)

Required mechanisms (each becomes its own future feature):

| Mechanism | What it means | Where it lives |
|---|---|---|
| **Shared agent memory** | `memory/agents/{agent}/MEMORY.md` is committed to a `headmaster-team-memory` repo (or a subdirectory of the team's main repo) and pulled at session start. Per-machine entries route to `memory/agents/{agent}/MEMORY.local.md`. | New `memory-shared/` dir, new hook `activate.py` step |
| **Project-level memory** | `memory/projects/{project}/` (repo registry, style profile, recurring patterns) committed alongside the project repo, not in HeadMaster. | New `projects.{slug}.memory_path` config key |
| **Shared config baseline** | Split `config.yml` → `config.yml` (shared, committed in team repo) + `config.local.yml` (per-dev overrides for `projects.active`, paths, `jira_push`). `ConfigResolver` merges them. | `scripts/config_utils.py` change |
| **Portable MCP** | `.mcp.json` drops `cmd /c` shape. `pyrun.js`-style platform detection writes the right form on first run. | `.mcp.json`, new `scripts/setup_mcp.py` |
| **Onboarding script** | `scripts/onboard.py` copies `.example` files, validates `node`/`python`, prompts for env vars, runs `setup-env`. | New script |
| **Per-stack permission profiles** | `settings.json` split into a JVM profile, a JS profile, a polyglot profile. User picks one during onboard. | New `.claude/profiles/` dir |
| **Feature collision handling** | Same slug taken by another dev on the same project → `init-feature` warns, offers a suffix. | `init-feature` SKILL change |
| **Team telemetry** | `monitoring.skill_tracking.*` keys (currently dead) wired to a real consumer that writes `memory/team-metrics.jsonl`, optionally pushed to a shared dashboard. | `run_logger.py` + new sink |

### Phase 3 — Enterprise (captured-only — not in scope for this plan)

SSO, RBAC per project, centralized telemetry dashboard, SBOM/IaC scanning, audit trail export, multi-region.

---

## 2. Rule File — `.claude/CLAUDE.md` stays the single source

HeadMaster is built on Claude Code. `.claude/CLAUDE.md` already serves as the contribution rule file. No `AGENTS.md` will be added in this plan.

What PR1–PR3 will tighten **inside** `.claude/CLAUDE.md`:

- **Unconditional human gates** — explicit list of paths (`.claude/agents/`, `.claude/skills/`, `.claude/workflows/`, `.claude/hooks/`, `scripts/gate_transition.py`, `scripts/state_manager.py`, `scripts/config_utils.py`, `.claude/settings.json`, `.mcp.json`).
- **Inventory discipline** — counts must come from `scripts/audit_inventory.py`, never hardcoded.
- **Config schema discipline** — every key must appear in `config.yml.example` and have a consumer; run `python scripts/config_utils.py validate config.yml` before committing.
- **Token efficiency** — replaces deleted `token_budgets` concept (decided in PR1).

Non-Claude AI agent support (`AGENTS.md` shim or full file) moves to **Phase 2 future scope** (see §4 below).

---

## 3. PR Sequence

Seven PRs, smallest blast-radius first. Each PR is independently revertible.

### PR1 — Doc + inventory drift (low risk, fast review)

**Scope (decided):** fix counts + remove dead commands + strip Phase D/E + remove `token_budgets`.

| File | Change |
|---|---|
| `README.md` | `12 agents` → `13`, `17 skills` → `18` in badges (lines 14–15) and tree (lines 752, 767). Add `retrospective-analyst` to agent table (insert under Planning or Execution, model: haiku, role: pattern extraction, pattern: Subagent). Add `retrospect` to supporting skills list. Remove Phase D/E mentions (lines 421–422 "A → B → C → D, no System Review"; line 884 "Phase E is mandatory for m/l"). Remove `token_budgets:` block from config reference (lines 571–576). |
| `.claude/CLAUDE.md` | Line 31: add `retrospective-analyst` to agent list, change `12 agents` → `13`. Line 45: add `retrospect` to skill list, change `17 skills` → `18`. Add a new "Token Efficiency" section (see below) replacing the deleted token_budgets concept. |
| `.claude/CLAUDE.md` (new section) | `## Token Efficiency`<br>- Each subagent prompt must include only what the current step needs. PRD, TDD, SYSTEM_DESIGN_NOTES are reference docs — extract sections, never pass whole.<br>- Skill instructions are hot code. State each rule once. No examples, no placeholders.<br>- Agent memory entries: one-line patterns, not narratives.<br>- `git diff` + ACs + extracted TDD section is the standard subagent payload — ≤5000 chars total. |
| `config.yml.sample` | Remove `pipeline.default_tier` (lines 57–61). Remove `session:` block (lines 67–73). Remove `monitoring:` block (lines 75–87). Remove `/switch-project` reference (line 12). Remove `/navigate` and `/switch-project` references (lines 125–126). |
| `.claude/workflows/classification.yml` | Line 8: replace `via /navigate {slug} --tier {new}` with `by editing loop_state.json.complexity_tier via gate_transition.py`. |
| `scripts/state_manager.py` | Lines 117, 205: replace `/navigate {slug}` suggestions with phase-appropriate commands (`/plan {slug}`, `/design {slug}`, `/execute {slug}`). |
| `.claude/skills/retrospect/SKILL.md` | Line 102: remove `/curate-memory` reference, replace with manual instruction: `Manually trim memory/agents/{agent}/MEMORY.md when it hits 200 lines (cap enforced by update_agent_memory.py).` |
| `scripts/skill_setup.py` | Remove `token_budgets` resolution (lines 103–107 and any return-dict inclusion). Remove from output JSON. |
| `scripts/audit_inventory.py` (new) | New script. Reads `.claude/agents/*.md` and `.claude/skills/*/SKILL.md` counts. Updates README badges + tree + CLAUDE.md lists in place (`--fix`) or fails (default). Wired to CI later. |
| `.claude/settings.json` | Dedupe `Bash(python scripts/*)` and `Bash(python .claude/hooks/*)` (each currently appears twice). |

PR1 acceptance:
- `grep -rn "/navigate\|/switch-project\|/curate-memory\|token_budgets\|Phase D\|Phase E" --include="*.md" .` returns 0 hits
- `python scripts/audit_inventory.py` exits 0
- All existing `pytest scripts/tests/` pass

---

### PR2 — Config schema consolidation (decided: single canonical example, no separate sample)

| File | Change |
|---|---|
| `config.yml.sample` | Delete. |
| `config.yml.example` (new) | Single canonical config with all real keys: `projects`, `pipeline.{max_loops, loop_caps, parallel, interactive}`, `autonomous`, `gates.{plan, design, breakdown}`, `security.impl_path_prefixes`, `projects.{slug}.confluence`. Inline comments explain each. No `session.*`, no `monitoring.*`, no `pipeline.default_tier`, no `pipeline.dry_run`, no `token_budgets`. |
| `scripts/config_utils.py` | Add 1-line schema validation: `validate(self) -> list[str]` returns list of unknown top-level keys (rejected against an `ALLOWED_KEYS` set). New CLI: `python scripts/config_utils.py validate config.yml` exits 0 / 1. |
| `.claude/hooks/activate.py` | Call `ConfigResolver(config_path).validate()` on session start. Print warning (not fatal) on unknown keys — keeps backward compat for users with extra keys. |
| `README.md` | Replace the two divergent config blocks (lines 524–576 and 622–630) with a single block that points to `config.yml.example`. |
| `.gitignore` | Already gitignores `config.yml` — confirm `config.yml.example` is NOT ignored. |
| `.claude/hooks/pre_spawn_validation.py` | No code change. README documents `security.impl_path_prefixes` (currently undocumented). |

PR2 acceptance:
- `python scripts/config_utils.py validate config.yml.example` exits 0
- `grep -rn "config.yml.sample" .` returns 0 hits

---

### PR3 — README "Who Can Use This" section + contribution rules in CLAUDE.md + audit hook

| File | Change |
|---|---|
| `README.md` | Replace the Best Practices section with a new "Who Can Use This" section (per §1 above). Phase 1 named users + limitations explicit; Phase 2 named as future scope with the eight team mechanisms table; Phase 3 captured-only. |
| `.claude/CLAUDE.md` | Add a "Contribution Rules" section: unconditional human-gate path list, inventory discipline (`scripts/audit_inventory.py`), config schema discipline (`python scripts/config_utils.py validate config.yml`), test requirements. Replaces the implicit/scattered rules. |
| `.github/PULL_REQUEST_TEMPLATE.md` (new) | PR template enforcing CLAUDE.md Contribution Rules: which PLAN.md PR it addresses, audit_inventory pass, config validate pass, test output. |
| `.github/workflows/audit.yml` (new) | GitHub Actions: on PR, run `python scripts/audit_inventory.py` and `python scripts/config_utils.py validate config.yml.example`. |

PR3 acceptance:
- README "Who Can Use This" section is present, no Best Practices section
- CLAUDE.md Contribution Rules section present
- CI workflow file present

---

### PR4 — Capability A: Broaden language coverage

Highest leverage given "going to be used heavily across different existing codebases."

| File | Change |
|---|---|
| `.claude/hooks/pre_spawn_validation.py` | Line 67: extend impl-path regex with `kt|kts|scala|swift|cs|fs|rs|php|rb`. Add `_DEFAULT_PREFIXES` entries: `cmd`, `pkg`, `crates`. |
| `.claude/skills/setup-env/SKILL.md` | Step 2 marker list: add `Cargo.toml`, `*.csproj`, `*.fsproj`, `composer.json`, `Gemfile`, `build.gradle.kts`. Step 4 table: add Cargo (`Cargo.toml` → `rust-version`), .NET (`*.csproj` → `TargetFramework`), Composer (`composer.json` → PHP version), Ruby (`Gemfile` → `ruby` directive). Step 4 `build_cmd`: cargo build, `dotnet build`, `composer install`, `bundle exec rake`. |
| `.claude/settings.json` permissions.allow | Add: `Bash(cargo *)`, `Bash(dotnet *)`, `Bash(rustc *)`, `Bash(composer *)`, `Bash(bundle *)`, `Bash(rake *)`, `Bash(go test *)`, `Bash(go build *)`, `Bash(pytest *)`, `Bash(ruff *)`, `Bash(mypy *)`. |
| `scripts/diff_review_filter.py` | Audit file-extension lists for matching coverage. |
| `tests/test_pre_spawn_validation.py` | Add test cases for `.kt`, `.cs`, `.rs`, `.swift` impl-path detection. |

PR4 acceptance:
- New test cases pass
- `setup-env --reset` on a Rust or .NET repo produces a valid `repo-registry.yml`

---

### PR5 — Capability B: Greenfield route

| File | Change |
|---|---|
| `.claude/skills/init-feature/SKILL.md` | Step 2 Route Detection: add `greenfield` route. Keywords: `bootstrap, scaffold, new repo, from scratch, greenfield, new service`. Step 2: route=greenfield → skip Q2 (Repository Discovery) → ask Q2-greenfield instead (target dir + stack + template). |
| `.claude/workflows/classification.yml` | Add `greenfield` route note: never reclassified; pipeline runs `plan-only` or `full` per user choice. |
| `.claude/skills/setup-env/SKILL.md` | Add Step 9 (greenfield): when invoked with `--greenfield <target-path>`, scaffold a starter repo (build file + `README.md` + `.gitignore`) per chosen stack, then proceed with normal scan. |
| `.claude/agents/codebase-analyst.md` | Failure mode `no matches`: when route=greenfield, return `GREENFIELD — no prior conventions, proceed without reference patterns` instead of plain "no matches". |
| `.claude/agents/developer.md` | Line 36 Convention discovery: when `reference_branch` empty AND route=greenfield → skip the "read 2 existing files" step, use stack-default conventions instead. |

PR5 acceptance:
- `/init-feature greenfield "new auth service"` produces a valid `FEATURE_INPUT.md` and scaffolds a target dir
- Existing non-greenfield routes unchanged

---

### PR6 — Capability C: Style/lint ingestion

| File | Change |
|---|---|
| `.claude/skills/setup-env/SKILL.md` | New Step 8: detect style/lint configs per repo — `.editorconfig`, `.eslintrc.*`, `eslint.config.*`, `checkstyle.xml`, `pyproject.toml [tool.black]`/`[tool.ruff]`, `.prettierrc`, `rustfmt.toml`, `.scalafmt.conf`. Extract rules into `memory/projects/{project}/style.md` (or per-repo `memory/projects/{project}/style/{repo}.md`). |
| `scripts/style_extractor.py` (new) | Per-config-type parsers. Output a compact markdown table: `Rule | Value | Source`. Cap 50 rules per repo. |
| `.claude/agents/developer.md` | Before "Convention discovery" step: read `memory/projects/{project}/style/{repo}.md` if present. Override `reference_branch` heuristic with explicit rules. |
| `.claude/agents/codebase-analyst.md` | Output Format: add `Style Rules` row when `style.md` present, summarize top 5 rules. |

PR6 acceptance:
- Running setup-env on a repo with `.editorconfig` produces `memory/projects/{p}/style/{repo}.md`
- `developer` agent reads that file before writing config or wiring code (manual test on a sample story)

---

### PR7 — Capability D: Mid-feature feedback loop

| File | Change |
|---|---|
| `.claude/skills/execute/stages/story-loop.md` | After Phase B PASS but before story complete: if `review-agent` produced findings of the same pattern ≥2 times in the same feature, append a one-line pattern to `memory/agents/developer/MEMORY.md` immediately (not wait for `/retrospect`). Dedup runs via `update_agent_memory.py` (already idempotent). |
| `scripts/recurring_finding_detector.py` (new) | Reads `docs/features/{project}/{slug}/execution/story-summaries.md` and review verdicts; groups findings by `(severity, owasp_category or rule_id)`; emits `agent_memory` proposals when count ≥ 2. |
| `.claude/agents/retrospective-analyst.md` | Note: feature-mid loop already captured recurring patterns; retrospective focuses on cross-feature signals only. |

PR7 acceptance:
- Manufactured a 2-story feature with the same review finding both times → entry appears in developer MEMORY.md before retrospect runs

---

### PR8 — `/curate-memory` skill (memory consolidation)

Re-introduces the skill that PR1 removed the reference to. PR1 was a clean strip; PR8 is the real build.

| File | Change |
|---|---|
| `.claude/skills/curate-memory/SKILL.md` (new) | Skill definition. Usage: `/curate-memory <agent>` or `/curate-memory --all`. Steps: load `memory/agents/{agent}/MEMORY.md` → group similar entries via `_word_overlap` (threshold 0.40, looser than the 0.60 dedup) → merge each group to the most recent phrasing → drop entries older than 90 days → write atomic with `.bak`. Reports lines-in, lines-out, groups merged, entries aged out. |
| `scripts/curate_agent_memory.py` (new) | Implementation. Reuses `_word_overlap` and `_memory_path` from `update_agent_memory.py`. CLI: `python scripts/curate_agent_memory.py <agent> [--age-days 90] [--threshold 0.40] [--dry-run]`. `--all` iterates every agent under `memory/agents/`. Always writes `.bak` before overwrite. Exits 0 on success, 1 on no-op (nothing to curate), 2 on error. |
| `scripts/update_agent_memory.py` | Line 69 error message: change `Run /compress first.` → `Run /curate-memory {agent} first.` (the existing reference to `/compress` is the wrong skill — `/compress` handles arbitrary .md files, not agent memory specifically). |
| `.claude/skills/retrospect/SKILL.md` | Re-add the line PR1 removed, in updated form: `When MEMORY.md approaches the 200-line cap, run /curate-memory <agent> to merge similar entries and drop entries >90 days old.` |
| `.claude/skills/retrospect/SKILL.md` | Add a Step 5 (Optional Suggestion): after applying agent_memory proposals, if any target agent's MEMORY.md is >150 lines, print `Suggestion: memory/agents/{agent}/MEMORY.md is at {N} lines. Consider /curate-memory {agent}.` |
| `scripts/tests/test_curate_agent_memory.py` (new) | Test cases: similar entries merge, dissimilar entries preserved, age-out works, dry-run does not write, `.bak` is created, cap-respecting (output ≤ 200 lines). |
| `.claude/CLAUDE.md` | In the existing "Agents" section, add to the agent-memory rules: `When MEMORY.md hits the cap, run /curate-memory <agent>.` |

PR8 acceptance:
- `python scripts/curate_agent_memory.py developer --dry-run` produces a diff preview without writing
- Running on a fixture MEMORY.md with 3 paraphrased entries reduces it to 1
- Entries dated >90 days old are removed
- `pytest scripts/tests/test_curate_agent_memory.py` passes
- After PR8 lands, `grep -rn "/curate-memory" .` returns valid references (retrospect/SKILL.md, update_agent_memory.py error, CLAUDE.md)

---

### PR9 — Phase A + B learning extraction (failure ledger → agent memory)

Today the per-story `failure_ledger.json` captures rich data — failed approach, `error_type`, `error_summary`, `files_touched`, `hypothesis` — but `failure_ledger.py cleanup` in story-loop wipes it before `/retrospect` ever runs. PR9 inserts a learning extraction step between Phase B PASS and ledger cleanup. Auto-applies to `developer` and `qa-engineer` memory only, with existing dedup.

**Classification (extractor):**

| ledger entry | Target agent |
|---|---|
| `error_type: build_failure / lint_error / runtime_error` | developer |
| `error_type: test_failure` AND `files_touched` ⊂ test paths | qa-engineer |
| `error_type: test_failure` AND `files_touched` includes impl paths | developer |
| `approach: phase_b_ac_check` AND `error_type: ac_coverage_gap` | developer |

**Confidence rule (when to write):**
- ≥2 ledger entries in this story with similar `approach` text (word-overlap ≥0.50) → write one consolidated memory line
- Single entry → write **only** if its `hypothesis` is concrete (not "unknown", "unclear", >10 words) — otherwise skip
- Always passes through `update_agent_memory.py` dedup (0.60 overlap against existing entries)

| File | Change |
|---|---|
| `scripts/extract_phase_learnings.py` (new) | Reads `memory/features/{project}/{slug}/failure_ledger.json` for a given STORY-KEY. Classifies each entry per the table above. Applies confidence rule. Generates one-line memory entries in the style: `{error_type} in {context}: {hypothesis-distilled}`. Calls `update_agent_memory.py {agent} append "{entry}"` for each. CLI: `python scripts/extract_phase_learnings.py {project} {slug} {STORY-KEY} [--dry-run]`. Exits 0 always (no-op is success). |
| `.claude/skills/execute/stages/story-loop.md` | "Story Complete" section, insert a new step **before** the existing `python scripts/failure_ledger.py cleanup {project} {slug} {STORY-KEY}` line: `python scripts/extract_phase_learnings.py {project} {slug} {STORY-KEY}`. Comment: `# Distill Phase A/B learnings to developer + qa-engineer memory before ledger cleanup`. |
| `.claude/skills/execute/stages/story-loop.md` (Phase A retry branch) | After "load failure ledger, retry with structurally different approach" — no change needed; the ledger still drives retry. PR9 only adds the post-success extraction. |
| `scripts/failure_ledger.py` | Add `summarize` subcommand: `python scripts/failure_ledger.py summarize {project} {slug} {STORY-KEY}` returns JSON `{entries: N, by_error_type: {...}, fix_files: [...]}`. Used by extractor. Cleaner than re-parsing the ledger inline. |
| `.claude/agents/developer.md` | Agent Memory section, add bullet: `Entries written automatically at story complete by scripts/extract_phase_learnings.py — patterns of build/lint/runtime/AC-coverage failures distilled from failure ledger.` |
| `.claude/agents/qa-engineer.md` | Agent Memory section, add same bullet, scoped to test-side fixes. |
| `.claude/skills/retrospect/SKILL.md` | Add a note in Step 2 (Spawn retrospective-analyst): `Phase A/B agent_memory entries have already been auto-applied at story complete (see scripts/extract_phase_learnings.py). retrospective-analyst focuses on cross-story signals only.` Avoids double-counting. |
| `.claude/agents/retrospective-analyst.md` | Add a constraint: `Do not propose agent_memory entries that duplicate per-story extractions. If a pattern already appears in developer or qa-engineer MEMORY.md (paraphrase included), skip.` Dedup at the source. |
| `scripts/tests/test_extract_phase_learnings.py` (new) | Test cases: (a) 2 build_failure entries with similar approach → one developer entry, (b) single test_failure with concrete hypothesis → one qa-engineer entry, (c) single entry with vague hypothesis ("unknown") → no write, (d) ac_coverage_gap → developer entry, (e) entry already in MEMORY.md → skipped by dedup, (f) `--dry-run` writes nothing. |

PR9 acceptance:
- Fixture with 2 similar build_failure ledger entries produces exactly 1 new line in `memory/agents/developer/MEMORY.md`
- Vague-hypothesis single entries do not produce memory writes
- `failure_ledger cleanup` still runs and removes the file
- `pytest scripts/tests/test_extract_phase_learnings.py` passes
- Manual integration: run a complete story with seeded ledger entries → memory updated → next retrospect run does not re-emit the same proposal

---

## 4. Future Scope Capture (referenced by Phase 2 of audience rollout)

Tracked here so the team-mode work has a single home and isn't re-derived later.

| Item | Phase | Owner (TBD) | Notes |
|---|---|---|---|
| Shared agent memory repo | 2 | — | New repo `headmaster-team-memory`; hook at session start syncs |
| Project-level memory committed to project repo | 2 | — | New `projects.{slug}.memory_path` |
| `config.yml` + `config.local.yml` split | 2 | — | Merge order: local overrides shared |
| Portable `.mcp.json` | 2 | — | Drop `cmd /c`, use platform shim |
| `scripts/onboard.py` | 2 | — | Copy `.example` files, validate runtimes, prompt env vars |
| Per-stack permission profiles | 2 | — | `.claude/profiles/jvm.json`, `js.json`, `polyglot.json` |
| Feature-slug collision handling | 2 | — | `init-feature` warn + suffix |
| Team telemetry sink | 2 | — | Wire `monitoring.skill_tracking` to `memory/team-metrics.jsonl` |
| Non-Claude AI agent support | 2 | — | Add `AGENTS.md` at repo root (tool-agnostic subset of CLAUDE.md rules) when Cursor/Aider/Copilot use becomes a real need |
| SSO / RBAC | 3 | — | Captured only |
| SBOM + IaC scan | 3 | — | Captured only |
| Audit-trail export | 3 | — | Captured only |

---

## 5. Sequencing + Review Gates

```
PR1 (Doc drift) ──► PR2 (Config schema) ──► PR3 (README + CLAUDE rules) ──► PR4 (Languages) ──► PR5 (Greenfield) ──► PR6 (Style) ──► PR7 (Feedback loop) ──► PR8 (curate-memory)
   1 day            1 day                    1 day                            2 days             2 days              2 days           3 days                  1 day
```

Each PR:
1. Approved by human (CLAUDE.md unconditional gate for pipeline/agent/skill edits)
2. CI: `audit_inventory` + `config_utils validate` + `pytest`
3. Merge to `main`
4. Next PR rebases on `main`

No PR merges if `AGENTS.md §9` checklist is incomplete.

---

## 6. Out of Scope (deliberately)

- Team enablement gaps from the original audit §8 — captured in Phase 2, not in PR1–PR7
- Versioning of agents/skills (audit §10 item 16) — defer until Phase 2 needs it
- Token-budget enforcement at runtime — replaced by CLAUDE.md token-efficiency guidance per user decision
