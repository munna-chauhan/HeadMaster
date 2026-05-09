# DISCOVER

**Pattern:** Tier-based isolation.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

**Goal:** ONE comprehensive session → complete requirements → solid PRD first time.

**Execution by tier:**

| Tier | Pattern | Depth | Isolation Reason |
|------|---------|-------|------------------|
| xs | skip | - | Out of scope |
| s | direct | 3-5 questions | Short session, notes naturally complete |
| m | subagent | 5-8 questions | Enforces complete notes, saves parent context |
| l | subagent | 8-12 questions | Complex, maximum discipline |

**Pattern = direct:** Load requirements-analyst in same session
**Pattern = subagent:** Spawn fresh, no parent context shared

**Check tier workflow:**
```bash
python scripts/workflow_config.py {tier} stages discovery status
```
- `skip` → HALT
- `optional` → check gaps: ≤2 skip, 3-5 ask user, 6+ run
- `required` → always run

**Steps:**

1. Read tier from loop_state.json → determine pattern (direct vs subagent)
2. Read FEATURE_DRAFT.md → gaps + questions
3. **Check for user message:** If `/plan slug message` was invoked with a message:
   - If FEATURE_DRAFT.md exists → message was appended to Section 6/7 by SKILL.md routing. Read updated gaps/questions.
   - If DISCOVERY_NOTES.md exists without YES → message was appended as answer. Read and continue from next unresolved question.
4. Determine depth: tier defaults + gap count + input_completeness

**If direct (s tier — inline resolution, no separate artifact):**

Question rules (inline — no agent file load):
- **P0 (Blocker):** missing business rule or undefined core behavior → must resolve via AskUserQuestion
- **P1 (Critical):** affects ≥2 PRD sections OR changes critical path → resolve via human or documented assumption
- **P2 (Nice-to-have):** single section impact → auto-resolve with `[Assumption: ...]`
- One question at a time. Cite the specific gap from FEATURE_DRAFT.md Section 6/7. Never ask what FEATURE_INPUT.md already answers.

Steps:
1. Read FEATURE_DRAFT.md Sections 6 (Gaps) and 7 (Questions)
2. For each P0/P1 gap: AskUserQuestion or auto-resolve if sufficient context available
3. For each P2 gap: auto-resolve with documented assumption
4. Rewrite FEATURE_DRAFT.md in-place: mark each gap as `[RESOLVED: {answer or assumption}]`
5. Append to end of FEATURE_DRAFT.md: `All Gaps Resolved: YES`
6. No DISCOVERY_NOTES.md written — FEATURE_DRAFT.md is the single source

Gate transition (s tier uses FEATURE_DRAFT.md):
```bash
python scripts/gate_transition.py {project} {slug} planning Draft --artifact docs/features/{project}/{slug}/planning/FEATURE_DRAFT.md
```

**If subagent (m/l tier):**
- **ISOLATION:** Do NOT load FEATURE_DRAFT.md into parent context
- Spawn requirements-analyst with minimal prompt:
  ```
  "Read FEATURE_DRAFT.md yourself. Run discovery per your agent definition.
  Ask 5-12 questions (tier {m|l}). Use AskUserQuestion format.
  Write DISCOVERY_NOTES.md with complete findings."
  ```
- Subagent reads files, conducts Q&A, writes artifact
- Parent receives only: DISCOVERY_NOTES.md

**DISCOVERY_NOTES.md format:**

Categories: Business Rules | UX | Edge Cases | Integration | Performance | Security

```
### Q{N}: {question}
**Category:** {category}
**Answer:** {answer}
**Source:** user | codebase:file:line | jira:KEY | confluence:page
```

End with: `All Questions Resolved: YES`

**Gate:** gate string present → auto-proceed to Draft.

```bash
python scripts/gate_transition.py {project} {slug} planning Draft --artifact docs/features/{project}/{slug}/planning/DISCOVERY_NOTES.md
```
