# Developer Workflow — Autonomous Mode

HeadMaster is configured for **minimal developer involvement**. Most decisions are automated, you review at key gates only.

## Quick Start

```bash
# Start a new feature
claude --name "my-feature"
/navigate "add user export API"

# HeadMaster auto-runs:
# - Classifies complexity (lite/standard/full)
# - Creates PRD (auto-resolves discovery questions from code/docs)
# - Generates system design + TDD
# - Breaks down into Jira stories (auto-creates epic if 3+ stories)
# - Implements all stories (tests first, atomic commits)
# - Reviews code + runs QA per story
# - Creates PR when all complete

# You're involved at:
# 1. /breakdown approval (review story list, approve/revise)
# 2. /execute escalations (if story hits max retry attempts)
# 3. PR merge (final human gate before main)
```

## What Runs Automatically (interactive: false)

### /plan Stage
- **Discovery questions:** Auto-answered from codebase/docs/Confluence
- **Ambiguity resolution:** Auto-selects best interpretation, logs rationale
- **PRD drafting:** Full 14-section PRD for complex features, 6-section for simple
- **Review:** Auto-approves if 0 blockers, auto-loops on findings (max 3 iterations)

### /design Stage
- **Architecture decisions:** Auto-selects patterns based on existing codebase
- **Tech stack choices:** Follows PRD Repos section, matches existing conventions
- **TDD generation:** Full 11-section blueprint for complex features
- **Review:** Auto-approves if passes checklist, auto-loops on findings

### /breakdown Stage
- **Story splitting:** Auto-classifies STORY/MERGE/SPLIT based on size/behavior
- **Epic creation:** Auto-creates epic if 3+ stories (auto-pushes to Jira)
- **Story estimation:** Auto-assigns SP (1-5 scale)
- **Human gate (unconditional):** You review JIRA_BREAKDOWN.md, approve/revise

### /execute Stage
- **Implementation:** Auto-implements per story (tests first, commits per AC)
- **Security scan:** Auto-runs, blocks on findings
- **Code review:** Auto-runs isolated subagent, loops back on critical/high findings
- **QA:** Auto-writes + runs integration tests, loops back on bugs
- **Escalation (unconditional):** If story hits max retries (3), stops for human input
- **System review:** Auto-runs after all stories complete
- **PR creation:** Auto-creates PR when system review passes

## When You're Asked (Confusion Clause)

Even in autonomous mode, HeadMaster stops if:
- **Ambiguity:** Two valid interpretations, wrong choice derails work
- **Contradiction:** Code vs docs vs Jira disagree on a fact
- **Missing input:** Required info absent, can't infer from context
- **Destructive action:** About to delete/overwrite something irreversible

These questions tagged `[CLARIFICATION]` — autonomous mode resumes after answer.

## Unconditional Gates (Always Manual)

1. **/breakdown Step 7:** Review story list before Jira push
2. **/execute escalation:** Story failed 3x, needs human intervention
3. **PR merge:** Final approval before merging to main

## Jira Integration (jira_push: true)

After /breakdown approval:
- Auto-creates epic (if 3+ stories)
- Auto-creates stories with labels, SP, ACs, relationships
- Auto-updates JIRA_BREAKDOWN.md with real Jira keys
- Auto-posts epic comment with breakdown summary

Requires env vars:
```bash
export JIRA_USER_EMAIL="your-email@syndigo.com"
export JIRA_API_TOKEN="your-api-token"
export ATLASSIAN_DOMAIN="syndigo.atlassian.net"
```

## Session Management

HeadMaster auto-manages context:
- **🟡 15 turns:** Notice (keep working)
- **🟠 25 turns:** Auto-braindump checkpoint to memory/ (non-blocking, keep working)
- **⛔ 35 turns:** Auto-handoff, start new session

Resume from checkpoint:
```bash
claude --name "my-feature"
/navigate my-feature-slug  # auto-detects phase, resumes from last gate
```

## Typical Feature Timeline

| Phase | Duration | Your Involvement |
|-------|----------|------------------|
| /plan | 5-10 min | None (auto) |
| /design | 10-15 min | None (auto) |
| /breakdown | 2 min | Approve story list |
| /execute (3-5 stories) | 30-60 min | None unless escalation |
| PR review | 5-10 min | Approve merge |

**Total developer time:** ~10-20 minutes across 1-2 hours end-to-end.

## Decision Log

All auto-decisions logged in:
- `docs/features/{slug}/planning/DISCOVERY_NOTES.md` — discovery resolutions
- `docs/features/{slug}/design/SYSTEM_DESIGN_NOTES.md` — ADRs (architecture decisions)
- `docs/features/{slug}/breakdown/JIRA_BREAKDOWN.md` — story classification rationale

Review these artifacts to understand HeadMaster's reasoning.

## Override Any Decision

At any gate, you can:
1. Edit the artifact directly (PRD.md, TDD.md, JIRA_BREAKDOWN.md)
2. Re-run the skill: `/plan {slug}`, `/design {slug}`, `/breakdown {slug}`
3. HeadMaster detects changes, adapts downstream work

## Parallel Execution (Optional)

For multi-repo features with independent stories:
```yaml
# config.yml
parallel: true  # /execute runs PARALLEL_GROUP stories simultaneously
```

Default: `false` (sequential execution, easier to debug)

## Rollback

If HeadMaster approved a gate prematurely:
```bash
python scripts/gate_transition.py {slug} rollback  # restores previous state
```

Then re-run the skill to fix the issue.

## Getting Help

- `/help` — Claude Code built-in help
- `CLAUDE.md` — HeadMaster project instructions
- `ARCHITECTURE.md` — Pipeline architecture reference
- GitHub issues: https://github.com/anthropics/claude-code/issues
