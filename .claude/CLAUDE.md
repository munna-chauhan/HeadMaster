# HeadMaster — Project Instructions

## Approach

- Think before acting. Read existing files before writing.
- Concise output but thorough reasoning.
- Prefer editing over rewriting whole files.
- Don't re-read files already read unless file may have changed.
- No sycophantic openers or closing fluff.
- Keep solutions simple and direct. No over-engineering.
- If unsure: say so. Never guess or invent file paths.
- User instructions always override this file.

## Efficiency

- Read before writing. Understand problem before coding.
- No redundant file reads. Read each file once per session.
- One focused coding pass. Avoid write-delete-rewrite cycles.
- Test once, fix if needed, verify once. No unnecessary iterations.
- Budget: 50 tool calls for single-phase tasks. Pipeline skills (/plan, /design, /breakdown, /execute) exempt — run
  until phase gate reached.
- For files >500 lines, use search tools to inspect specific sections. Don't read entire file unless necessary.
- Use `--name` flag to name sessions: `claude --name "my-feature"` for easy resume.

## Context Discipline

- **Load only what current phase requires.** Don't pre-load artifacts from future phases or re-read artifacts from
  phases already completed and distilled forward.
- **Respect distillation chain.** Each phase distills upstream work into richer artifact. Once distilled, trust output —
  don't reach back to source it was built from.
- **Extract, don't hold.** When reading large external data (APIs, documents, raw files), extract only what's relevant
  to current task. Don't retain full content in context after extraction.
- **Search before reading.** For any document >500 lines, search for relevant section first. Read full document only
  when full document is task.
- **Read once, reference many times.** Never re-read file already read in same session unless it may have changed.
- **Scope to your role.** Load only what current responsibility requires. If reviewing, need artifact under review and
  its direct predecessors — not full pipeline history.
- **Master Index rule.** If document exceeds 800 lines, treat as Master Index with linked sub-files. Read index first,
  then load only sub-files relevant to current task.

## Initialization

On every new session:

1. Read `config.yml` — project key, jira_push, max_loops, parallel, interactive. If absent → HALT:
   `config.yml missing. Copy config.yml.example and fill in project_key.`
2. Scan `docs/features/` for in-progress features:
    - For plan (Init→Review): check `planning/PRD.md` for gate string, or working files for in-progress stage
    - For design (Architect→Review): check `design/` artifacts + `loop_state.json`
    - For execute: read `JIRA_BREAKDOWN.md` Execution Log — last entry = resume point
    - For merge gate: check `execution/reviews/` for system-review

Don't read example files or skill files at init. Load them only when skill invoked.

## Config

`config.yml` — single file at repo root, read directly. Missing keys use skill defaults.

**interactive** (default: `true`) — controls agent decision behavior:

- `interactive: true` → ask user at ambiguous decision points via AskUserQuestion
- `interactive: false` → auto-select best option, log rationale, never ask

All skills and agents read this from config.yml. Agents labeled "Autonomous mode" follow this flag.

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
- **Execution phase context must be scoped.** Don't instruct inline phases to read files beyond their scope. Execution
  phases (implement, scan, review, qa) run in main session — minimize context before each phase via /handoff+/clear.
- **Reviewer sub-agents (prd-reviewer, tdd-reviewer):** Pass artifact path only. Reviewer reads artifact fresh — never
  instruct it to use the parent's already-loaded copy.
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

Routes are recommended sequences, not prisons — any phase can be invoked standalone.

## Quality Standards

- Every artifact: standard header (Technical Owner, AI Co-Author, Date).
- PRDs: 14 sections. TDDs: 11 sections. Anything less is incomplete.
- Review loops: max 3 iterations before human escalation.

## Security

- Never print API keys, passwords, or tokens in output.
- Jira credentials in env vars: `ATLASSIAN_DOMAIN`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`.
- Never execute `rm -rf`, `git reset --hard`, `git clean -fd`, `drop table`, `DROP DATABASE`, `TRUNCATE`, `DELETE`
  without WHERE clause, or `git push --force` without explicit human approval.
- Primary shell: PowerShell. Use `cmd /c "..."` only when necessary.

## Diagrams

draw.io is optional. Before generating any diagram:

1. Run `where drawio` (Windows) to check if installed.
2. If found → use `/draw {slug} "{description}"` → saves to `docs/features/{slug}/diagrams/`.
3. If not found → fall back to inline Mermaid. Note in artifact: `[Mermaid fallback — draw.io not installed]`.

Never block a phase because draw.io is absent. Mermaid is always acceptable for simple flows.
For complex multi-service architecture diagrams, add a note recommending draw.io install.

## Recovery

- **Undo Claude's file edits:** Press `Esc`+`Esc` to open checkpoint picker — select checkpoint to restore code,
  conversation, or both.
- **Free context space:** Start new session and reference memory files — session handoffs in `memory/features/{slug}/`
  capture all context.
- **Resume after crash:** `/navigate {slug}` detects exact phase from artifacts. `/execute {slug}` resumes from last
  Execution Log entry.

## Memory

Two memory scopes — both valid, different purposes:

**Feature-scoped:** `memory/features/<slug>/agents/<agent>.md`

- Per-story working context: files touched, patterns found, retry history
- Written by sub-agents during /execute. Scoped to one feature. Discarded after feature ships.

**Agent-scoped:** `memory/agents/<agent-name>/`

- Cross-feature learnings: codebase conventions, recurring patterns, false positives suppressed
- Written by agents at session end. Persists across features.

Other feature memory: `memory/features/<slug>/` — loop state, decisions, open questions, session handoffs.
Summarize ruthlessly — capture insight, discard detail. Delete session files once internalized.

## File Conventions

- `docs/features/<slug>/planning/` — PRD.md, FEATURE_DRAFT.md, DISCOVERY_NOTES.md, PRD_REVIEW.md
- `docs/features/<slug>/design/` — SYSTEM_DESIGN_NOTES.md, TDD*.md, TDD_REVIEW.md, MIGRATION_PLAN.md
- `docs/features/<slug>/diagrams/` — draw.io + PNG exports
- `docs/features/<slug>/breakdown/` — JIRA_BREAKDOWN.md
- `docs/features/<slug>/execution/reviews/` — security-scan-*.md, code-review-*.md, qa-report-*.md, escalation-*.md
- `docs/features/<slug>/retrospective/` — system-review.md
- `docs/features/<slug>/input/` — Jira JSON + extracted .md, Confluence JSON + extracted .md, local-docs/
- Examples: `docs/examples/`
- Config: `config.yml` (repo root)
- Scripts: `scripts/` (jira_ops.py, secret_scanner.py)