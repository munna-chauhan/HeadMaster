# HeadMaster — Architecture Reference

## Model Routing

Model set by `Model:` field in each sub-agent prompt. Agent frontmatter is fallback if prompt omits it. Skills must
always specify `Model:` explicitly in sub-agent prompts.

| Task Type                               | Model               | Agents                                                                     | Reason                             |
|-----------------------------------------|---------------------|----------------------------------------------------------------------------|------------------------------------| 
| Creative design, architecture decisions | `claude-opus-4-7`          | solutions-architect                                                        | Needs deep reasoning               |
| Code generation, implementation         | `claude-sonnet-4-6`        | developer, tdd-author                                                      | Balanced cost/quality              |
| Orchestration, Q&A, planning            | `claude-sonnet-4-6`        | requirements-analyst, prd-author, release-agent, qa-engineer, review-agent | Conversational + structured output |
| Mechanical checklist, search, scan      | `claude-haiku-4-5-20251001` | prd-reviewer, tdd-reviewer, codebase-analyst, web-researcher               | No creativity needed               |
| Hook validation (Stop/SubagentStop)     | `claude-haiku-4-5-20251001` | inline hook agents                                                         | Lightweight gate check only        |
| Main session (orchestrator)             | `claude-sonnet-4-6` | —                                                                          | Intent parsing, routing, user Q&A  |

**Cost guard:** Never spawn opus for review, scan, or search tasks. Never spawn sonnet for checklist-only tasks.

---

## Context Budget

Main agent context discipline before spawning any sub-agent:

- **Load only phase inputs.** Before spawning, hold only: config.yml values (cached as text), current phase artifact
  paths, structured context object to pass.
- **Never pass raw files to sub-agents.** Pass structured context objects with extracted fields. Sub-agent reads its own
  files.
- **Execution phase context must be scoped.** Phases A (implement) and B (security-scan) run inline in main session.
  Phases C (review-code), D (qa-integration), and E (review-system) run as isolated subagents — same pattern as
  prd-reviewer and tdd-reviewer. This ensures genuine cognitive isolation between author and reviewer.
- **Reviewer sub-agents (prd-reviewer, tdd-reviewer, review-agent in Phase C/E, qa-engineer in Phase D):** Pass
  artifact path only. Reviewer reads artifact fresh — never instruct it to use the parent's already-loaded copy.
- **Max files in sub-agent prompt:** 3 files for reviewers, 1 repo per codebase-analyst instance.
- **Retry context:** Pass failure delta only — not full prior attempt context.

---

## Layer Architecture

| Layer    | Path                | Invoke                    | Purpose                                         |
|----------|---------------------|---------------------------|-------------------------------------------------|
| Skills   | `.claude/skills/`   | `/skill-name`             | SDLC process definitions (primary entry points) |
| Commands | `.claude/commands/` | `/command-name`           | Atomic git/utility operations                   |
| Agents   | `.claude/agents/`   | Loaded by skills (Step 0) | Behavioral constraints and output standards     |

**Pipeline skills (5):** `/plan`, `/design`, `/breakdown`, `/execute`, `/navigate`
**Execution phase skills (5):** `/implement`, `/security-scan`, `/review-code`, `/qa-integration`, `/review-system`
**Utility skills (3):** `/jira-ops`, `/draw`, `/compress`
**Commands (5):** `/commit`, `/create-branch`, `/create-pr`, `/handoff`, `/ask-user` (question format)
**Scripts (10):** `compress.py`, `gate_transition.py`, `failure_ledger.py`, `convergence_check.py`, `secret_scanner.py`, `jira_ops.py`, `input_extractor.py`, `diff_scanner.py` (security engine), `test_infra_detector.py`, `git_guard.py`
**Hooks (8):** `activate.py`, `feature_context.py`, `session_reset.py`, `token_budget.py`, `read_compressor.py`, `post_tool.py`, `statusline.py`, `auto_braindump.py`
**Stop Checks (4):** `plan_stop.py`, `design_stop.py`, `breakdown_stop.py`, `execute_stop.py` (located in `.claude/hooks/stop_checks/`)

## Hook Consolidation (2026-04-21)

Merged 3 hooks (mode_tracker.py, tool_call_tracker.py, write_compressor.py) → `post_tool.py`.
**Reason:** Saves ~200ms per tool call. Single PostToolUse handler now:
  1. Increments tool_calls counter in session-budget.json
  2. Compresses memory/*.md writes (opt-in, 4KB+ files, 5%+ savings)
  3. Removed mode tracking (skill context from prompt now, not hook state)

**Benefits:**
- Faster hook execution (1 process vs 3)
- Simpler maintenance (single file vs 3)
- No shared state complexity

See commit ae1a1c6 for migration details.

---

## Auto-Braindump (2026-04-21)

**Problem:** Long-running skills (`/execute` with many stories) hit ⛔ threshold mid-execution, terminating before completion.

**Solution:** Progressive checkpoint at 🟠 threshold (default 25 turns):
- `token_budget.py` triggers `auto_braindump.py` at orange
- Writes compressed state: `memory/features/{slug}/session-{ts}-auto-braindump.md`
- **Does NOT terminate** — execution continues
- Provides recovery point if session crashes before completion

**Benefits:**
- Long-running features can complete even if session age exceeds normal threshold
- Automatic recovery points every 25 turns
- No manual `/handoff` needed during execution
- If ⛔ hits, user has checkpoint to resume from

**Trigger:** Automatic at `turn_warn_orange` (configurable in `config.yml`).

Routes are recommended sequences, not prisons — any phase can be invoked standalone.

---

## Memory Architecture

HeadMaster uses two distinct memory systems:

**1. Feature-scoped (HeadMaster):** `memory/features/<slug>/`
- **Purpose:** Session state, pipeline progress, handoffs
- **Lifecycle:** Created during feature work, discarded after feature ships
- **Contents:**
  - `loop_state.json` — pipeline phase, iteration counts, complexity tier
  - `session-{timestamp}.md` — manual handoffs via /handoff command
  - `session-{timestamp}-auto-braindump.md` — automatic checkpoints at orange threshold
  - `open_questions.md`, `draft_context.md` — phase-specific artifacts
  - `agents/*.md` — per-story agent context (developer, qa-engineer, review-agent retry history)
- **Management:** Written by HeadMaster skills, read by SessionStart hooks

**2. Agent-scoped (Claude Code):** `.claude/agent-memory/<agent-type>/`
- **Purpose:** Cross-feature learnings, codebase patterns, conventions
- **Lifecycle:** Persists until project deleted
- **Contents:** Automatic agent memories (codebase patterns, build quirks, conventions)
- **Management:** Handled by Claude Code Agent tool (not HeadMaster skills)
- **Examples:** `web-researcher/`, `codebase-analyst/`, `developer/`

**Key distinction:** Feature memory is ephemeral (per-feature), agent memory is permanent (per-project).
