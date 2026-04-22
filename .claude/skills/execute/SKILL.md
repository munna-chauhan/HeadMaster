---
name: execute
description: "Drives JIRA_BREAKDOWN.md stories to completion. Per story: implement (inline) → scan (script) → review (subagent) → qa (subagent). System review (subagent) after all stories. Never writes code directly."
argument-hint: <feature-slug>
hooks:
  Stop:
    - hooks:
      - type: command
        command: "python .claude/hooks/stop_checks/execute_stop.py $ARGUMENTS"
        timeout: 10
  PostToolUse:
    - matcher: "Bash"
      hooks:
      - type: prompt
        model: haiku
        timeout: 15
        prompt: |
          Bash command ran. Parse $ARGUMENTS as JSON.
          If command contains 'git merge' and exit code != 0:
            Return {"ok": false, "reason": "Merge failed — conflict. Escalate."}
          If command contains 'git push' and exit code != 0:
            Return {"ok": false, "reason": "Push failed. Check remote state."}
          All other: return {"ok": true}
---

# Execute

Load `.claude/agents/release-agent.md`. Verify `config.yml` exists at repo root. If absent → HALT. Read values: `parallel`, `interactive`.

Mission: drive all stories to completion. Phase A (implement) + Phase B (scan) run inline. Phase C (review), Phase D (QA), and Phase E (system review) spawn as isolated subagents for genuine cognitive isolation (via Agent tool, not /handoff). **Never write code.**

---

## Context Rules

- Load JIRA_BREAKDOWN.md once at init — extract story list, cache as text
- Load repo map from PRD (Repos section for full tier, or from JIRA_BREAKDOWN.md story entries for lite/standard)
- Never hold full TDD or PRD in context during execution
- Each phase reads only what it needs from disk

---

## Stage Dispatch

Based on current execution state, load and execute the corresponding stage file:

| State                    | Action                                                          |
|--------------------------|-----------------------------------------------------------------|
| Not started / resuming   | Load and execute `.claude/skills/execute/stages/setup.md`       |
| Stories ready            | Load and execute `.claude/skills/execute/stages/story-loop.md`  |
| All stories done / escalation | Load and execute `.claude/skills/execute/stages/finalize.md` |

---

## Status Values

| Status         | Phase          |
|----------------|----------------|
| ⏳ NEW          | Not started    |
| 🔄 IN PROGRESS | implement      |
| 🔍 SCANNING    | security-scan  |
| 👁️ IN REVIEW  | review-code    |
| 🧪 IN QA       | qa-integration |
| ✅ COMPLETE     | Done           |
| ❌ FAILED       | Escalated      |
| ⚪ DEFERRED     | Skipped        |

---

## Prerequisites

- `docs/features/{slug}/breakdown/JIRA_BREAKDOWN.md` — human-approved
- `docs/features/{slug}/design/TDD*.md` OR `docs/features/{slug}/design/IMPLEMENTATION_BRIEF.md` — exists
- `docs/features/{slug}/planning/PRD.md` — PRD Status: APPROVED
