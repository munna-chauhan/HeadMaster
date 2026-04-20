# HeadMaster — Architecture Reference

## Model Routing

Model set by `Model:` field in each sub-agent prompt. Agent frontmatter is fallback if prompt omits it. Skills must
always specify `Model:` explicitly in sub-agent prompts.

| Task Type                               | Model               | Agents                                                                     | Reason                             |
|-----------------------------------------|---------------------|----------------------------------------------------------------------------|------------------------------------| 
| Creative design, architecture decisions | `claude-opus-4-7`   | solutions-architect                                                        | Needs deep reasoning               |
| Code generation, implementation         | `claude-sonnet-4-6` | developer, tdd-author                                                      | Balanced cost/quality              |
| Orchestration, Q&A, planning            | `claude-sonnet-4-6` | requirements-analyst, prd-author, release-agent, qa-engineer, review-agent | Conversational + structured output |
| Mechanical checklist, search, scan      | `claude-haiku-4-5`  | prd-reviewer, tdd-reviewer, codebase-analyst, web-researcher               | No creativity needed               |
| Hook validation (Stop/SubagentStop)     | `claude-haiku-4-5`  | inline hook agents                                                         | Lightweight gate check only        |
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
**Commands (4):** `/commit`, `/create-branch`, `/create-pr`, `/handoff`
**Scripts (8):** `gate_transition.py`, `failure_ledger.py`, `metrics.py`, `secret_scanner.py`, `diff_scanner.py`, `git_guard.py`, `input_extractor.py`, `input_sanitizer.py`

Routes are recommended sequences, not prisons — any phase can be invoked standalone.
