---
name: plan
description: "Smart planning. Two modes: /plan <slug> (auto-detect + resume), /plan <slug> <message> (act on intent). Raw input → finalized PRD. Working files kept for traceability."
argument-hint: <feature-slug> [message]
hooks:
  Stop:
    - hooks:
        - type: agent
          model: haiku
          timeout: 30
          prompt: |
            Check if planning is complete or legitimately paused.
            Context: $ARGUMENTS

            Use Read tool to check:
            1. Does docs/features/*/planning/PRD.md exist with 'PRD Status: APPROVED' at end?
               - If PRD exists but lacks gate string → planning incomplete
            2. Does docs/features/*/planning/DISCOVERY_NOTES.md end with 'All Questions Resolved: YES'?
               - If exists without YES → discovery incomplete

            Also check last_assistant_message in context:
            - If it contains 'AskUserQuestion' → waiting for user, ok to pause
            - If it contains 'max_loops exceeded' or 'escalating to human' → ok to stop
            - If it contains 'PRD Status: APPROVED' → ok to stop

            Return {"ok": true} if complete or legitimately paused.
            Return {"ok": false, "reason": "<specific what is missing>"} if work remains.
---

# Plan

Mission: Raw input → finalized PRD. Single source of truth = `PRD.md`. Working files temporary.

---

## Modes

**`/plan <slug>`** — auto-detect state, act.

- No feature dir → look for `FEATURE_INPUT.md` in repo root. Not found → ask user.
- Feature exists → resume from last state.
- PRD finalized → report status. Nothing to do.

**`/plan <slug> <message>`** — parse intent.

- No feature → use `<message>` as description. Start fresh.
- In progress → continue from last state, treat message as context.
- PRD finalized → reopen, apply feedback, re-validate.

---

## Stages

| Stage    | Pattern          | Agent                         | Working File       | Output             |
|----------|------------------|-------------------------------|--------------------|--------------------|
| Init     | Skill + subagent | `codebase-analyst` (parallel) | FEATURE_DRAFT.md   | —                  |
| Discover | Direct           | `requirements-analyst`        | DISCOVERY_NOTES.md | —                  |
| Draft    | Direct           | `prd-author`                  | —                  | PRD.md             |
| Review   | Subagent         | `prd-reviewer`                | —                  | PRD.md (validated) |

Flow: `Init → Discover → Draft → Review`
Loop-backs: `DISCOVERY_GAP` → Discover. `PRD_ISSUE` → Draft. Mixed → Discover first.

Working files (FEATURE_DRAFT.md, DISCOVERY_NOTES.md) kept until user explicitly requests cleanup or feature is fully
shipped. PRD.md = primary source of truth after approval.

---

## State Detection

Check `docs/features/{slug}/planning/`:

```
PRD.md + gate string                     → FINALIZED (report status, or reopen if message)
PRD.md + no gate string + loop_state blocker → Review loop-back in progress
PRD.md + no gate string                  → start Review
DISCOVERY_NOTES.md ends with YES         → resume Draft
DISCOVERY_NOTES.md without YES           → resume Discover
FEATURE_DRAFT.md exists                  → resume Discover
Nothing                                  → start Init
```

Gate string (end of PRD.md):

```
PRD Status: APPROVED
```

---

## Setup (every invocation)

1. Read `config.yml` → `project_key`, `max_loops` (default 3), `interactive`
2. Check `memory/features/{slug}/loop_state.json` → loop count
3. Detect state
4. If `<message>`: parse intent

---

## INIT

**Pattern:** Skill orchestrates. Launches `codebase-analyst` as subagent for codebase scan.

**Steps:**

**1. Generate slug** — lowercase, hyphens, max 40 chars. Create `docs/features/{slug}/` dir.

- `interactive: true` → confirm via AskUserQuestion
- `interactive: false` → auto-select, log choice

**2. Resolve input** (priority order):

- `<message>` arg → save to `docs/features/{slug}/input/raw-input.md`
- `FEATURE_INPUT.md` in repo root
- Neither → AskUserQuestion: what to plan?

**3. Fetch external data** (skip silently if creds missing):

Use MCP tools first (Tier 1), fall back to jira_ops.py (Tier 2):

```
# Jira epic
mcp__atlassian__jira_get_issue({issueKey: "{EPIC-KEY}"})
  → pipe JSON through: python3 scripts/input_extractor.py from-mcp-jira input/jira/{EPIC-KEY}.md

# Jira stories under epic
mcp__atlassian__jira_search_issues({jql: "parent={EPIC-KEY} AND status NOT IN (Done,Closed)"})
  → pipe JSON through: python3 scripts/input_extractor.py from-mcp-jira input/jira/{EPIC-KEY}-stories.md

# Confluence pages (by page ID from FEATURE_INPUT.md)
mcp__atlassian__confluence_get_page({pageId: "{PAGE-ID}"})
  → pipe JSON through: python3 scripts/input_extractor.py from-mcp-confluence input/confluence/{PAGE-ID}.md
```

Fallback if MCP unavailable:

```
python3 scripts/jira_ops.py get-issue {EPIC-KEY} > input/jira/{EPIC-KEY}.json
python3 scripts/input_extractor.py jira input/jira/{EPIC-KEY}.json input/jira/{EPIC-KEY}.md
```

Never use bash `> file` redirection with MCP. Capture result then write. Fetch fail → warn + continue.
Downstream stages read `.md` files only — never raw `.json`.

**4. Launch codebase-analyst subagent** (after step 3 — uses enriched description from Jira if available):

```
Agent: codebase-analyst
Model: haiku
Prompt:
"Respond concisely throughout.
Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths/commands exact.

Scan codebase for feature: {feature-description-enriched-from-jira-if-available}
Find:
- Entry points + integration boundaries touching this feature
- Existing patterns to mirror (file:line refs)
- Blast radius — classes/services/endpoints affected
- Data model: affected entities, schema, migrations
- Conflicts: breaking changes, backward compat risks
If codebase empty or no matches found: return 'greenfield — no existing patterns' per section.
Return findings as compressed markdown tables."
```

After subagent returns:

**5. Merge subagent findings** into FEATURE_DRAFT.md System Context + Data Model sections.

**5b. Extract input files** (after fetch, before writing FEATURE_DRAFT):

```
python3 scripts/input_extractor.py dir docs/features/{slug}/input/
```

This strips API metadata from all fetched JSON files and saves lean `.md` equivalents alongside them.
Saved ~70-85% tokens. Downstream stages (Discover, Draft) read the `.md` files, not the raw `.json`.
Fetch fail or no JSON files → skip silently.

**6. Move** `FEATURE_INPUT.md` repo root → `docs/features/{slug}/input/FEATURE_INPUT.md`

**7. Write** `docs/features/{slug}/planning/FEATURE_DRAFT.md`

Frontmatter:

```yaml
---
feature:
  slug: { slug }
  name: { name }
  type: spike|hotfix|story|feature|epic
  owner: { author }
  created: { ISO-date }
jira:
  epic_key: { key or null }
status:
  stage: Init
  last_updated: { ISO-date }
---
```

Header:

```
**Technical Owner:** {from input or Jira}
**AI Co-Author:** requirements-analyst (AI-Generated)
**Date:** {ISO-date}
**Feature Folder:** docs/features/{slug}
```

8 sections:

1. **High-Level Goal** — user narrative preserved, no formalization
2. **Data Sources** — all inputs (Jira, Confluence, codebase, text)
3. **System Context** — entry points, integration boundaries, blast radius (from subagent)
4. **Data Model Implications** — affected entities, schema changes, migrations (from subagent)
5. **Conflicts & Migration Concerns** — breaking changes, backward compat (from subagent)
6. **Identified Gaps** (min 3) — ambiguities, contradictions, missing info
7. **Open Questions** (min 2) — tagged P0 (blocker), P1 (important), P2 (nice-to-know)
8. **Repos** — name, role, tech stack

**Gate:** FEATURE_DRAFT.md exists + ≥3 gaps + ≥2 open questions → auto-proceed to Discover.

---

## DISCOVER

**Pattern:** Direct. Load `.claude/agents/requirements-analyst.md` for behavioral constraints before executing.
Interactive — needs user back-and-forth.

**On loop-back entry:** read loop_state.json → check `iteration` against `max_loops`. If exceeded → escalate to human,
stop.

**Task tracking:** Use `TaskCreate`/`TaskUpdate`/`TaskList` to track each question as a task across turns. Create one
task per question when identified. Update status as: `pending` → `resolved` (answered) | `deferred` (user skipped, P2) |
`blocked` (needs external input). Check `TaskList` at start of each turn to know what remains.

**Steps:**

1. Read FEATURE_DRAFT.md → extract gaps + questions. On loop-back: also read loop_state findings.
2. For each question: `TaskCreate({title: "[PLAN] Q{N}: {question}", status: "pending", priority: "{P0|P1|P2}"})`
3. Classify gaps:
    - Resolvable from codebase → `[RESOLVED FROM CODE]`
    - Resolvable from Jira/Confluence → `[RESOLVED FROM DATA]`
    - Needs user → Q&A queue (apply AskUserQuestion format below)
3. After all questions resolved: `TaskUpdate` each to `resolved`. Write DISCOVERY_NOTES.md.

**DISCOVERY_NOTES.md format:**

Categories: Business Rules | UX | Edge Cases | Integration | Performance | Security

Per question:

```
### Q{N}: {question}
**Category:** {category}
**Answer:** {answer}
**Source:** user | codebase:file:line | jira:KEY | confluence:page
```

End with:

```
All Questions Resolved: YES
```

**Gate:** `All Questions Resolved: YES` at end of file → auto-proceed to Draft.

---

## DRAFT

**Pattern:** Direct. Load `.claude/agents/prd-author.md` for behavioral constraints before executing.

**On loop-back entry:** read loop_state.json → check `iteration` against `max_loops`. If exceeded → escalate to human,
stop.

**Gate conditions (before starting):**

- FEATURE_DRAFT.md exists
- DISCOVERY_NOTES.md ends with `All Questions Resolved: YES`
- Missing → halt, return to Init/Discover

**Inputs (read once, in order):**

1. FEATURE_DRAFT.md — vision + gaps
2. DISCOVERY_NOTES.md — resolved decisions
3. `input/` — fallback only. Prefer `.md` extracted files over raw `.json` (extractor runs during Init).

On loop-back: read loop_state findings. Fix flagged sections only.

**Write** `docs/features/{slug}/planning/PRD.md`

Header:

```
**Technical Owner:** {from FEATURE_DRAFT.md}
**AI Co-Author:** Product Analyst (AI-Generated)
**Date:** {ISO-date}
**Feature Folder:** docs/features/{slug}
**Confidence:** {1-10}/10 — {rationale for downstream design success}
```

14 sections:

1. **Executive Summary** — 3-5 sentences: overview, users, value, MVP
2. **Background & Business Context** — problem, pain, why now
3. **Goals & Success Metrics** — quantified ("export -40%", "p99 < 200ms")
4. **Functional Requirements** — FR-1, FR-2... no source annotations
5. **Non-Functional Requirements** — Perf/Reliability/Security/Scale, quantified
6. **User Stories** — INVEST-compliant, testable ACs, cover concurrency/ordering/dedup
7. **Assumptions & Constraints** — `[Assumption]` + justification
8. **Dependencies** — systems, teams, approvals, APIs
9. **Out of Scope** — exclusions + justification
10. **Open Questions** — genuinely unresolved only
11. **Risks & Mitigations** — business + technical
12. **Repos** — name, role, tech stack, build command (one row per repo)
13. **Acceptance Criteria** — feature pass/fail for sign-off
14. **Appendix** — glossary, links

Rules: no omissions (N/A + reason if empty), no source annotations in body, no references to FEATURE_DRAFT.md or
DISCOVERY_NOTES.md anywhere in PRD, diagrams only when clearer than prose.

**Diagram decision rule:**

| Diagram type             | When to use                | Tool                                                        |
|--------------------------|----------------------------|-------------------------------------------------------------|
| User flow / process flow | >3 steps with branches     | Mermaid `flowchart` (simple) or `/draw` (complex branching) |
| System context           | services + external actors | `/draw` — layout matters                                    |
| Gantt / phasing          | S12 roadmap with 3+ phases | Mermaid `gantt` only                                        |
| State machine            | status transitions         | Mermaid `stateDiagram` (simple) or `/draw` (many states)    |

Use `/draw {slug} "{diagram description}"` → saves to `docs/features/{slug}/diagrams/`.
Use Mermaid inline only for simple linear flows (≤5 nodes, no crossing arrows).
Never use Mermaid for architecture or multi-service diagrams — arrows always messy.

**NO_PRIOR_KNOWLEDGE_TEST:** Could engineer unfamiliar with codebase implement from PRD alone? If no → add context.

**Gate:** 14 sections present, no source annotations, all metrics quantified → proceed to Review.

---

## REVIEW

**Pattern:** Launch `prd-reviewer` as isolated subagent. Fresh context — no authorship memory.

**Output artifact:** `docs/features/{slug}/planning/PRD_REVIEW.md`

```
Agent: prd-reviewer
Model: haiku
Prompt:
"Respond concisely throughout.
Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths/commands exact.

Review PRD cold — no prior context on this feature.
Read as engineer implementing alone 6 months from now.

Inputs (read once, in order — STOP after step 2 unless C1/C2 fails):
1. docs/features/{slug}/planning/PRD.md — document under review
2. docs/features/{slug}/planning/DISCOVERY_NOTES.md — resolved decisions (source of truth)
3. docs/features/{slug}/planning/FEATURE_DRAFT.md — original vision (read ONLY if C1/C2 needs verification)

Do NOT read input/ folder. Do NOT read Jira/Confluence files.
If C1/C2 requires verifying a specific version number or field name:
  Read ONLY the specific file mentioned in PRD (e.g. FEATURE_DRAFT.md Section 2).
  Never read the entire input/ directory.

Execute every checklist item. Record PASS/FAIL/N/A before moving to next. No item skipped.

A — STRUCTURE
  A1 All 14 sections present + populated (N/A+reason acceptable, empty = FAIL)
  A2 No inline source annotations in body (no 'per Jira', 'as discussed', 'see Confluence')
  A3 No references to FEATURE_DRAFT.md or DISCOVERY_NOTES.md in PRD body
  A4 Section 10 contains only genuinely unresolved questions
  A5 Section 9 out-of-scope items have justification
  A6 Header has Technical Owner + Confidence score

B — COMPLETENESS
  B1 Every discovery decision in DISCOVERY_NOTES reflected in FRs/NFRs/constraints
  B2 Every gap from FEATURE_DRAFT addressed or explicitly deferred in Section 10
  B3 Every FR has at least one corresponding AC in Section 13
  B4 Concurrency/ordering/dedup edge case covered in at least one user story
  B5 Failure/offline/dependency-down scenario in NFRs or Section 11
  B6 All repos in Section 12 have defined role + build command
  B7 No open infrastructure questions blocking implementation

C — ACCURACY
  C1 Version numbers in PRD match FEATURE_DRAFT + raw inputs
  C2 Field names/API shapes in PRD match raw inputs (not just DISCOVERY_NOTES transcription)
  C3 Counts/limits/thresholds consistent across all PRD sections
  C4 All [Assumption] items have justification
  C5 No internal contradictions between sections

D — SELF-CONTAINEDNESS
  D1 Every FR implementable without opening any other document
  D2 Every NFR implementable without opening any other document
  D3 Every AC testable without opening any other document
  D4 Glossary defines all domain terms used in body

E — DEVELOPER FRICTION
  E1 Every metric has number + unit + percentile (not 'fast', 'large', 'soon')
  E2 Every AC starts with observable behavior, not implementation step
  E3 Error response schemas defined for all failure paths in FRs
  E4 Every FR answers: what to build, who uses it, when it triggers
  E5 Section 13 criteria measurable without author present

Severity per finding:
  BLOCKER — missing section, contradicts decision, unfeasible, blocks downstream design
  HIGH    — incomplete section, gap engineer must guess around
  MEDIUM  — inconsistency, minor gap, defer to TDD acceptable
  LOW     — typos, style, cleanup

Blocker type per finding:
  PRD_ISSUE      — PRD writing problem → fix in Draft
  DISCOVERY_GAP  — unresolved business rule → loop to Discover

Fix MEDIUM/LOW inline in PRD.md directly.
BLOCKER/HIGH → record in findings table, do not fix.

Write PRD_REVIEW.md with:
1. Executive Summary — verdict, blocker counts, strengths, critical gaps
2. Checklist Results — every item as PASS/FAIL/N/A
3. Traceability Matrix — every FR + NFR mapped to source (DISCOVERY_NOTES Q# or [Assumption])
4. Findings table:
   | # | Item | Severity | Type | Section | Issue | Fix |
5. Resolution Plan — blockers, high priority, acceptable risks, verdict

Verdict:
  APPROVED    — 0 BLOCKERs, 0 HIGHs
  CONDITIONAL — 0 BLOCKERs, HIGHs present (proceed after fixing HIGHs)
  REJECTED    — any BLOCKER present"
```

**On subagent return:**

If APPROVED or CONDITIONAL:

1. Append to PRD.md:
   ```
   ---
   PRD Status: APPROVED
   Approved: {ISO-date}
   Iterations: {N}
   ```
2. CONDITIONAL → log HIGH findings as tech debt, do not block progression

If REJECTED (any BLOCKER):

1. Read current `memory/features/{slug}/loop_state.json` → get existing iteration count
2. Write updated loop_state:
   ```json
   {"stage": "Review", "iteration": previous+1, "blocker_type": "PRD_ISSUE|DISCOVERY_GAP", "findings": [...], "timestamp": "ISO"}
   ```
3. Check `iteration` against `max_loops` from config — if exceeded → escalate to human, stop
4. Any `DISCOVERY_GAP` blocker → write to `memory/features/{slug}/open_questions.md`, return to Discover
5. All `PRD_ISSUE` blockers → return to Draft
6. Mixed → Discover first, then Draft

---

## AskUserQuestion Format

Load: `ToolSearch → query: "select:AskUserQuestion"`

### Decision Rule

Ask only if:

- Two valid options exist with real trade-offs + no clear winner from code/context/Jira/Confluence
- A class/file is missing that materially affects requirements (flag as risk question)
- A business rule has two contradictory sources (flag as conflict question)

Never ask:

- Anything resolvable from codebase, Jira, Confluence, or config
- Generic questions ("how should we handle errors?", "what format?")
- Questions where one option is clearly better given context

Autonomous mode (`interactive: false`): auto-select best option, log rationale, never ask.

### Question Format

One question at a time. Acknowledge each answer before next question.

```
AskUserQuestion({
  "questions": [{
    "header": "Label (12 chars)",
    "question": "Q{n} [{category}] [{priority}]: {Specific question with full context.}\n\nWhy this matters: {impact on PRD/downstream phases if wrong}\n\nFound: {what code/Jira/Confluence shows — cite source}",
    "multiSelect": false,
    "options": [
      {
        "label": "Option A (Recommended)",
        "description": "✅ {pros} / ⚠️ {cons}"
      },
      {
        "label": "Option B",
        "description": "✅ {pros} / ⚠️ {cons}"
      },
      {
        "label": "Flag as risk — decide later",
        "description": "Document as [OPEN QUESTION] P{priority} in PRD Section 10. Unblocks progress."
      }
    ]
  }]
})
```

**Priority tags:**

- `P0` — blocks PRD approval. Must resolve before Draft stage.
- `P1` — important. Resolve before Review stage.
- `P2` — nice-to-know. Can defer to TDD or implementation.

**Category tags:**
`Business Rules` · `Edge Cases` · `Integration` · `Performance` · `Security` · `Data Model` · `API Contract`

### After Each Answer

```
✅ Q{n}: {summary of answer chosen}
{If follow-up needed}: Q{n+1} builds on this — {why}
```

Adaptive follow-ups: use previous answers to shape next question. If user chose async → ask about retry strategy. If
user chose sync → skip queue questions.

### User Navigation Commands

Respond to these at any point during Q&A:

- `progress` → show Q{done}/{total}, list resolved answers so far
- `summary` → show all answers recorded so far
- `skip` → mark current question P2, move to next
- `back` → revisit previous question, update answer
- `stop` → halt Q&A, record remaining as `[OPEN QUESTION]` in output

### Multiselect (when applicable)

Use `"multiSelect": true` only when multiple options can genuinely coexist (e.g. "which edge cases apply?"). Never use
for mutually exclusive decisions.

---

## Reopen Finalized PRD

`/plan <slug> <message>` on APPROVED PRD:

1. Read PRD.md + parse intent from `<message>`
2. Minor feedback → edit sections directly → run Review
3. New requirement → add to relevant sections → run Review
4. Major change → recreate DISCOVERY_NOTES.md for new questions only. FEATURE_DRAFT.md still exists (kept) — use as
   base.
5. Remove `PRD Status: APPROVED`
6. Run Review stage
7. On pass → re-add gate string

---

## Loop State

Path: `memory/features/{slug}/loop_state.json`

```json
{
  "planning": {
    "iteration": 1,
    "last_blocker_type": null,
    "last_stage": "Review",
    "status": "PASS",
    "findings": []
  }
}
```

---

## Completion

```
Planning complete: {slug}

PRD.md — 14/14 sections
Confidence: {N}/10
Iterations: {N}
Working files retained for traceability.

Next: /design {slug}
```

---

## Prerequisites

- Feature description (text/Jira/Confluence) or `FEATURE_INPUT.md` in repo root
- `config.yml` at repo root
