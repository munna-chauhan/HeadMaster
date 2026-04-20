<div align="center">

<img src="./HeadMaster_Logo.png" alt="HeadMaster Logo" width="175"/>

### 🎯 **ADLC — Agentic Development Lifecycle**

*You describe a feature. AI writes the PRD, designs the system, implements the code, runs security scans, reviews it,
and opens the PR. You approve the decisions and merge.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Required-D97706?style=flat&logo=anthropic&logoColor=white)](https://docs.anthropic.com/en/docs/claude-code)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat)](LICENSE)

</div>

---

## Why HeadMaster?

Traditional SDLC is **human-driven with AI assistance**.
ADLC flips that — **AI drives the full development lifecycle** while humans own the key decisions.

HeadMaster automates the entire lifecycle — not just code generation, but the full SDLC from idea to production PR —
using a structured pipeline of specialized AI agents, each with a single job and a non-negotiable quality gate.

```
You type:   /navigate "Add rate limiting to the public API"

AI does:    Requirements Q&A → PRD → System design + ADRs
            → TDD blueprint → Jira stories → Code + tests → Security scan
            → Code review → QA integration tests → System audit → PR

You do:     Approve requirements · Sign off architecture · Merge the PR
```

**Nothing ships without your approval. Every gate is explicit. The AI drives — you own the decisions.**

---

## How It Works

```mermaid
graph LR
    A([💡 Your idea]) --> B[📋 Plan\nPRD · Q&A · Review]
B -->|PRD approved| C[🏗️ Design\nArchitecture · TDD · Review]
C -->|TDD approved|D[📦 Breakdown\nStories · Jira · Human gate]
D -->|You approve|E[⚙️ Execute\nCode · Scan · Review · QA]
E -->|All stories done|F[🚀 Merge Gate\nPR · Human merges]

style A fill: #e3f2fd, stroke: #1565c0
style F fill: #fca5a5, stroke: #dc2626
```

Each arrow is a hard gate — the pipeline cannot advance until the gate condition is met. No skipping, no shortcuts.

| You provide                   | AI handles                       | You decide              |
|-------------------------------|----------------------------------|-------------------------|
| Feature description           | PRD (6, 10, or 14 sections)     | ✅ Requirements approval |
| Jira ticket / Confluence page | System design + ADRs             | ✅ Architecture sign-off |
| Bug description               | Code + unit tests                | ✅ Story prioritization  |
|                               | Security scan + code review      | ✅ Final PR merge        |
|                               | Integration tests + system audit |                         |

---

## Complexity Tiers

Not every feature needs a 14-section PRD and 11-section TDD. HeadMaster auto-classifies complexity at `/navigate` and
scales artifact depth accordingly:

| Tier | Stories | PRD Sections | Design Artifact | Review |
|------|---------|-------------|-----------------|--------|
| **Lite** | 1-2, single repo | 6 | IMPLEMENTATION_BRIEF.md (5 sections) | No TDD review |
| **Standard** | 3-5, 1-2 repos | 10 | TDD.md (8 sections) | TDD review |
| **Full** | 6+, multi-repo | 14 | TDD.md (11 sections) or TDD_MASTER + per-repo TDDs | TDD review |

Override anytime: `/navigate <slug> --tier <lite|standard|full>`

Lite tier skips the Architect stage entirely — goes straight from PRD to IMPLEMENTATION_BRIEF to breakdown.

---

## Delivery Routes

Not every change needs the full pipeline. HeadMaster picks the right process:

```mermaid
flowchart LR
    R{Change type?}
    R -->|research / PoC| spike["🔬 spike\nHours"]
    R -->|production bug| hotfix["🔧 hotfix\nHours"]
    R -->|single story| story["📖 story\n1-3 days"]
    R -->|new capability| feature["✨ feature\n1-3 weeks"]
    style spike fill: #fffde7, stroke: #f9a825
    style hotfix fill: #fff3e0, stroke: #ef6c00
    style story fill: #e8f5e9, stroke: #2e7d32
    style feature fill: #e3f2fd, stroke: #1565c0
```

| Route         | When to use                   | Phases                       |
|---------------|-------------------------------|------------------------------|
| 🔬 **spike**  | Research, PoC, feasibility    | Prototype → Decision         |
| 🔧 **hotfix** | Production bug, config fix    | Implement → Review → PR      |
| 📖 **story**  | Single story, known approach  | Implement → Review → QA → PR |
| ✨ **feature** | New capability needing design | Full pipeline above          |

> **Large initiatives:** The feature pipeline handles multi-repo work natively. `/design` produces per-repo TDDs,
`/breakdown` builds a dependency graph with parallel groups. No separate epic route needed — the pipeline scales.

---

## Quick Start

### Prerequisites

| Tool                                                          | Required    | Notes                                                        |
|---------------------------------------------------------------|-------------|--------------------------------------------------------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | ✅           | The AI runtime HeadMaster runs inside                        |
| Python 3.10+                                                  | ✅           | Hooks and scripts                                            |
| Git                                                           | ✅           | Branch management, commits                                   |
| draw.io desktop                                               | ⚠️ Optional | Architecture diagrams — auto-falls back to Mermaid if absent |
| Jira access                                                   | ⚠️ Optional | Story push — skipped if credentials absent                   |

### 1. Install

```bash
git clone <repository>
cd HeadMaster
pip install -r requirements.txt
```

**Set up your local Claude Code settings:**

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
```

Then edit `.claude/settings.local.json` — update the draw.io path for your machine:

- **Windows:** `C:\\Program Files\\draw.io\\draw.io.exe *`
- **macOS:** `/Applications/draw.io.app/Contents/MacOS/draw.io *`
- **Not installed:** remove that line entirely — diagrams fall back to Mermaid

### 2. Configure

**`config.yml`** — edit at repo root:

```yaml
project_key: "PROJ"    # Jira project key. Leave empty if no Jira.
jira_push: false       # true = push stories to Jira after human approval
max_loops: 3           # Max review iterations before human escalation
parallel: false        # true = run independent stories simultaneously
interactive: true      # true = ask at decision points. false = auto-decide, log rationale
default_tier: "full"   # Default complexity tier if /navigate can't determine. Options: lite, standard, full
```

> Epic key is **not** in config — it's per-feature. Provide it in `FEATURE_INPUT.md` or as a Jira link. `/breakdown`
> resolves and stores it in `JIRA_BREAKDOWN.md` for that feature only.

**Credentials** — Windows environment variables only, never in config files:

```powershell
# Permanent (survives reboots) — run once
[System.Environment]::SetEnvironmentVariable("ATLASSIAN_DOMAIN", "yourcompany.atlassian.net", "User")
[System.Environment]::SetEnvironmentVariable("JIRA_USER_EMAIL", "you@company.com", "User")
[System.Environment]::SetEnvironmentVariable("JIRA_API_TOKEN", "your-api-token", "User")
```

Get your Jira API token at: https://id.atlassian.com/manage-profile/security/api-tokens

### 3. Verify

```bash
python .claude/hooks/activate.py        # should print project key + feature status
python scripts/secret_scanner.py --file config.yml   # should print "scan passed"
python scripts/jira_ops.py health       # only if using Jira
where drawio                            # optional — falls back to Mermaid if absent
```

Expected:

```
[HeadMaster] Project: PROJ
[HeadMaster] No active features. Run /navigate to start.
```

### 4. Start

```bash
# Name your session — enables easy resume across conversations
claude --name "my-feature"

# Then start with a description
/navigate "Add rate limiting to the public API"
```

> `/navigate` classifies the route and complexity tier, detects any existing progress, and tells you exactly what to run
> next. Always start here when unsure.

---

## Skills Reference

### Pipeline

| Skill        | What it does                                             | Usage                             |
|--------------|----------------------------------------------------------|-----------------------------------|
| `/navigate`  | Dashboard · route classifier · tier assessment · resume  | `/navigate [slug or description]` |
| `/plan`      | Requirements: Init → Discover → Draft → Review           | `/plan {slug} [message]`          |
| `/design`    | Design: Architect → Engineer → Review                    | `/design {slug} [message]`        |
| `/breakdown` | TDD → stories · Jira push · merge gate                   | `/breakdown {slug} [merge-gate]`  |
| `/execute`   | Per-story: implement → scan → review → QA → system audit | `/execute {slug}`                 |

Each pipeline skill uses **lazy-loaded stage files** — only the active stage's instructions are loaded into context,
keeping token usage minimal. For example, `/plan` dispatches to `stages/init.md`, `stages/discover.md`,
`stages/draft.md`, or `stages/review.md` based on detected state.

### Execution Phases *(run by `/execute` per story)*

| Phase         | Skill             | Gate                                          |
|---------------|-------------------|-----------------------------------------------|
| A — Implement | `/implement`      | Build green · all tests pass                  |
| B — Security  | `/security-scan`  | 0 secrets · 0 critical CVEs · 0 critical SAST |
| C — Review    | `/review-code`    | 0 critical · 0 high findings                  |
| D — QA        | `/qa-integration` | All ACs PASS · regression green               |
| E — Audit     | `/review-system`  | 0 actionable findings                         |

### Utilities

| Skill / Command | What it does                                                          |
|-----------------|-----------------------------------------------------------------------|
| `/draw`         | Architecture diagrams via draw.io (Mermaid fallback if not installed) |
| `/compress`     | Compress memory/working files — saves tokens every session            |
| `/jira-ops`     | Jira API: fetch, create, update, link, transition                     |
| `/commit`       | Atomic commit with secret scan + conventional format                  |
| `/handoff`      | Save session state (≤100 lines) + clear context                      |
| `/create-pr`    | Validate branch hierarchy + create PR with human gate                 |

---

## Agents & Model Routing

12 specialists — one job each. Model assignment is intentional cost discipline:

| Agent                  | Job                                 | Model                          |
|------------------------|-------------------------------------|--------------------------------|
| `solutions-architect`  | System design + ADRs                | **opus** — deep reasoning only |
| `requirements-analyst` | Surface gaps, Q&A                   | sonnet                         |
| `prd-author`           | Write PRD (6/10/14 sections)        | sonnet                         |
| `tdd-author`           | Implementation blueprints           | sonnet                         |
| `developer`            | Code + tests per TDD                | sonnet                         |
| `review-agent`         | Code review + system audit          | sonnet                         |
| `qa-engineer`          | Integration tests                   | sonnet                         |
| `release-agent`        | Story breakdown + merge gate        | sonnet                         |
| `prd-reviewer`         | Stress-test PRD (24-item checklist) | **haiku** — mechanical only    |
| `tdd-reviewer`         | Stress-test TDD (27-item checklist) | **haiku**                      |
| `codebase-analyst`     | Trace code (file:line refs)         | **haiku**                      |
| `web-researcher`       | Research APIs, libraries            | **haiku**                      |

Opus for architecture only. Haiku for checklists and search. Sonnet for everything else. Never spawn opus for review or
scan tasks.

---

## Token & Cost Control

HeadMaster has layered token reduction built in:

| Layer                    | What it does                                                 | Saving                    |
|--------------------------|--------------------------------------------------------------|---------------------------|
| Model routing            | Right model for each task                                    | 60-80% vs opus everywhere |
| Complexity tiers         | Lite features produce 6-section PRD, not 14                  | 40-60% fewer artifacts    |
| Lazy stage loading       | Skills split into stage files — only active stage loaded     | 250-350 lines saved/skill |
| Deterministic stop hooks | Python scripts replace haiku agents for gate checks          | ~10 haiku calls saved     |
| `read_compressor` hook   | Compresses memory + input `.md` reads before Claude sees them | 30-60% per read          |
| `input_extractor`        | Strips Jira/Confluence API noise on fetch                    | 70-85% per input file     |
| `/compress` skill        | Compresses memory/working files persistently                 | 38-60% per file           |
| Context discipline       | Each phase loads only what it needs                          | Prevents 2-3x bloat      |
| Auto-handoff             | Saves state at turn limit, clears context                    | Prevents runaway cost     |

**Session age tracking** — turn-based (the only reliable signal without API token counts):

| Threshold      | Action                                 |
|----------------|----------------------------------------|
| 🟡 15 turns    | Notice — session getting long          |
| 🟠 25 turns    | Warning — run `/handoff` soon          |
| ⛔ 35 turns    | Auto-handoff written + context cleared |

> Heavy file reads (>500KB) downgrade thresholds by 5 turns. Run `/handoff` proactively at 🟠.

**Security scanning tools** — all optional. Missing tools are reported, never silently skipped:

| Tool                                | Language | Install                                        |
|-------------------------------------|----------|------------------------------------------------|
| `bandit`                            | Python   | `pip install bandit`                           |
| `pip-audit`                         | Python   | `pip install pip-audit`                        |
| `eslint` + `eslint-plugin-security` | JS/TS    | `npm install -g eslint eslint-plugin-security` |
| `npm audit`                         | JS/TS    | Bundled with Node.js                           |
| `mvn` + OWASP Dependency Check      | Java     | Maven + plugin                                 |

---

## Reliability Features

### Convergence Checking
Review loops (Plan Review, Design Review) use `convergence_check.py` to detect oscillation — if a blocker that was
previously resolved reappears, the system escalates to human instead of looping forever. Uses word-overlap normalization
so the same issue described differently is still caught.

### Failure Ledger
When `/implement` fails, the failure is recorded in an append-only ledger (`failure_ledger.py`). On retry, the developer
agent must read all prior failures and choose a structurally different approach. 70%+ word overlap with a prior failed
approach triggers a warning.

### Crash Recovery
If a session dies mid-`/execute` (token limit, network, terminal closed), the resume pre-flight checks each IN PROGRESS
story branch for dirty working trees and broken builds before continuing. Offers to stash, reset, or escalate.

### Subagent Artifact Validation
After every review subagent returns (PRD review, TDD review), the system validates the expected artifact file exists on
disk and contains the expected verdict structure before advancing the pipeline. Missing or malformed artifacts trigger a
retry, then escalation.

### Git Guard
`git_guard.py` runs as a PreToolUse hook on every Bash command. Blocks destructive operations (`push --force`,
`reset --hard`, `rebase`, `cherry-pick`, `filter-branch`) and validates branch names match HeadMaster conventions.
Fail-closed: unknown git subcommands are blocked by default.

---

## Artifact Structure

Every feature gets its own workspace under `docs/features/{slug}/`:

```
docs/features/{slug}/
├── input/                     ← Jira, Confluence, local docs (raw + extracted .md)
├── planning/
│   ├── FEATURE_DRAFT.md       ← Init output
│   ├── DISCOVERY_NOTES.md     ← Q&A resolved
│   ├── PRD.md                 ← ✅ Source of truth after approval
│   └── PRD_REVIEW.md          ← Review findings
├── design/
│   ├── SYSTEM_DESIGN_NOTES.md ← Architecture + ADRs (standard/full tier)
│   ├── IMPLEMENTATION_BRIEF.md← Design output (lite tier only)
│   ├── TDD.md                 ← Single repo (or TDD_MASTER + TDD_{REPO} for multi)
│   ├── TDD_REVIEW.md          ← Checklist review (standard/full tier)
│   ├── MIGRATION_PLAN.md      ← Conditional
│   └── diagrams/              ← draw.io + PNG (or Mermaid fallback)
├── breakdown/
│   └── JIRA_BREAKDOWN.md      ← Stories + execution tracker
├── execution/reviews/
│   ├── security-scan-*.md
│   ├── code-review-*.md
│   ├── qa-report-*.md
│   └── escalation-*.md        ← Failed stories with full failure ledger
└── retrospective/
    └── system-review.md       ← Post-execution design-vs-actual audit

memory/features/{slug}/        ← Loop state, failure ledgers, session handoffs
memory/agents/{name}/          ← Cross-feature agent learnings
```

---

## Directory Structure

```
HeadMaster/
├── .claude/
│   ├── skills/                 # 13 skills (pipeline + execution + utility)
│   │   ├── plan/
│   │   │   ├── SKILL.md        # Dispatch + state detection (~94 lines)
│   │   │   └── stages/         # Lazy-loaded: init, discover, draft, review
│   │   ├── design/
│   │   │   ├── SKILL.md        # Dispatch + state detection (~130 lines)
│   │   │   └── stages/         # Lazy-loaded: architect, engineer, review
│   │   ├── execute/
│   │   │   ├── SKILL.md        # Dispatch (~60 lines)
│   │   │   └── stages/         # Lazy-loaded: setup, story-loop, finalize
│   │   ├── breakdown/SKILL.md
│   │   ├── navigate/SKILL.md
│   │   └── ...                 # implement, security-scan, review-code, qa-integration, etc.
│   ├── agents/                 # 12 AI specialists
│   ├── commands/               # 5 atomic operations (commit, handoff, create-pr, etc.)
│   ├── workflows/              # 5 route definitions + complexity tiers
│   ├── hooks/
│   │   ├── stop_checks/        # 4 deterministic Python gate checks
│   │   ├── read_compressor.py  # PreToolUse — compress memory/input reads
│   │   ├── write_compressor.py # PostToolUse — compress memory writes only
│   │   ├── token_budget.py     # UserPromptSubmit — turn-based session tracking
│   │   ├── git_guard.py        # PreToolUse — block destructive git ops (via scripts/)
│   │   └── ...                 # activate, feature_context, session_reset, etc.
│   ├── CLAUDE.md               # System prompt (~71 lines)
│   └── ARCHITECTURE.md         # Model routing + context budget reference
│
├── scripts/                    # 11 Python utilities
│   ├── gate_transition.py      # Atomic pipeline state transitions
│   ├── convergence_check.py    # Review loop oscillation detection
│   ├── failure_ledger.py       # Append-only retry history per story
│   ├── metrics.py              # Per-feature JSONL event collection
│   ├── diff_scanner.py         # Security scan: secrets + SAST + deps
│   ├── secret_scanner.py       # Pre-commit secret detection
│   ├── git_guard.py            # Branch validation + destructive op blocking
│   ├── input_extractor.py      # Strip Jira/Confluence API noise → lean .md
│   ├── input_sanitizer.py      # Prompt injection detection in external data
│   ├── jira_ops.py             # Jira API operations
│   └── test_infra_detector.py  # Detect available test infrastructure per repo
│
├── docs/
│   ├── features/{slug}/        # Feature workspaces (generated)
│   └── examples/               # 4 artifact samples
│
├── memory/                     # Persistent state (generated)
│   ├── features/{slug}/        # Per-feature: loop_state, failure ledgers, handoffs
│   └── agents/{name}/          # Cross-feature agent learnings
│
├── config.yml                  # Project configuration
└── requirements.txt            # Python dependencies
```

---

## Branch Strategy

```
story/{STORY-KEY}  →  feature/{slug}  →  main
      ↑ auto-merge        ↑ PR + human gate (always)
```

- `story → feature` — direct merge, no PR
- `feature → main` — PR required, human merges, no exceptions
- Merge conflict → halt + escalate to human

---

## Troubleshooting

| Problem               | Fix                                                                                                              |
|-----------------------|------------------------------------------------------------------------------------------------------------------|
| Feature not resuming  | `/navigate {slug}` — detects phase from artifacts                                                                |
| Undo Claude's changes | `Esc + Esc` → checkpoint picker                                                                                  |
| Review loop stuck     | Check `memory/features/{slug}/loop_state.json` → `last_blocker_type`                                             |
| Jira push failing     | `echo $env:ATLASSIAN_DOMAIN` · verify `jira_push: true` in config                                                |
| Build failing         | Check `execution/reviews/escalation-{STORY-KEY}.md`                                                              |
| Session too long      | `/handoff` — saves state, clears context, session continues                                                      |
| draw.io not found     | Falls back to Mermaid automatically. Install from [diagrams.net](https://www.diagrams.net/) for complex diagrams |
| Hook errors           | Check `~/.claude/.HeadMaster-hook-errors.log` — statusline shows ⚠️ if errors in current session                |
| Crash mid-execute     | `/execute {slug}` — pre-flight checks branch integrity before resuming                                           |

---

## Examples

See `docs/examples/` for artifact samples:

`FEATURE_DRAFT` · `PRD_REVIEW` · `code-review` · `qa-report`

---

<div align="center">

```bash
claude --name "my-feature"
/navigate "describe your feature here"
```

*HeadMaster takes it from there.*

</div>
