---
name: design
description: "Technical design pipeline. /design <slug> (auto-detect + resume, reads PRD by default), /design <slug> <message> (focus hint or override). PRD → SYSTEM_DESIGN_NOTES + TDD(s). Working files kept."
argument-hint: <feature-slug> [message]
hooks:
  Stop:
    - hooks:
        - type: agent
          model: haiku
          timeout: 30
          prompt: |
            Check if design is complete or legitimately paused.
            Context: $ARGUMENTS

            Use Read tool to check:
            1. Does docs/features/*/design/SYSTEM_DESIGN_NOTES.md contain 'Architecture Locked: YES'?
               - If exists without lock → architect stage incomplete
            2. Does docs/features/*/design/TDD_REVIEW.md exist?
               - If TDD files exist but no TDD_REVIEW.md → review not run yet
            3. Does TDD_REVIEW.md contain 'APPROVED' or 'CONDITIONAL'?
               - If contains 'REJECTED' → blockers unresolved

            Also check last_assistant_message in context:
            - If contains 'AskUserQuestion' → waiting for user, ok to pause
            - If contains 'max_loops exceeded' or 'escalating to human' → ok to stop
            - If contains 'APPROVED' or 'CONDITIONAL' verdict → ok to stop

            Return {"ok": true} if complete or legitimately paused.
            Return {"ok": false, "reason": "<specific what is missing>"} if work remains.
  SubagentStop:
    - hooks:
        - type: prompt
          model: haiku
          timeout: 15
          prompt: |
            A subagent just finished. Parse $ARGUMENTS as JSON.
            Check the 'last_assistant_message' field.

            For codebase-analyst subagents:
              Valid output contains: a markdown table OR the word 'greenfield'.
              Invalid: empty string, 'I cannot', 'no results', or fewer than 20 words.

            For tdd-reviewer subagents:
              Valid output contains: 'APPROVED', 'CONDITIONAL', or 'REJECTED'.
              Invalid: missing all three verdict words.

            For other subagents: return {"ok": true} — no validation needed.

            Return {"ok": true} if output is valid.
            Return {"ok": false, "reason": "Subagent returned incomplete output: <what was missing>"} if invalid.
  PostToolUseFailure:
    - matcher: "Bash"
      hooks:
        - type: command
          command: |
            python3 -c "
  import json, sys
  data = json.load(sys.stdin)
  cmd = data.get('tool_input', {}).get('command', '')
  err = data.get('error', 'unknown error')
if 'jira_ops' in cmd:
  out = {'hookSpecificOutput': { 'hookEventName': 'PostToolUseFailure', 'additionalContext':
                                                                          f'External data fetch failed: { err }. Continue with partial data. Mark affected SYSTEM_DESIGN_NOTES sections as [ UNVERIFIED ].' } }
  print(json.dumps(out))
  "
        statusMessage: "Handling script failure..."
---

# Design

Load agent per stage (see Stage table). Read `config.yml`.

Mission: PRD → implementation-ready TDD(s). Single source of truth per stage. Working files kept.

---

## Modes

**`/design <slug>`** — auto-detect state, act.

- No design dir → read PRD.md, start Architect stage.
- Design in progress → resume from last state.
- TDD approved → report status. Nothing to do.

**`/design <slug> <message>`** — parse intent.

- `<message>` = focus hint: narrows attention, does not replace any step. Log: `Focus: {message}`.
- In progress → continue from last state with focus hint.
- Approved → reopen, apply feedback, re-validate.

---

## Stages

| Stage     | Pattern           | Agent                                                 | Output                                                                       |
|-----------|-------------------|-------------------------------------------------------|------------------------------------------------------------------------------|
| Architect | Skill + subagents | `solutions-architect` + `codebase-analyst` (parallel) | SYSTEM_DESIGN_NOTES.md                                                       |
| Engineer  | Direct            | `tdd-author`                                          | TDD.md or TDD_MASTER.md + TDD_{REPO}.md(s) + MIGRATION_PLAN.md (conditional) |
| Review    | Subagent          | `tdd-reviewer`                                        | TDD_REVIEW.md                                                                |

Flow: `Architect → Engineer → Review`
Loop-backs: `TDD_ISSUE` → Engineer. `DESIGN_GAP` → Architect. Mixed → Architect first.

---

## State Detection

Check `docs/features/{slug}/design/`:

```
TDD_REVIEW.md + APPROVED verdict + loop_state design.status=PASS  → COMPLETE
TDD file(s) exist + loop_state DESIGN_GAP                        → resume Architect
TDD file(s) exist + loop_state TDD_ISSUE                         → resume Engineer
TDD file(s) exist + no APPROVED verdict                          → resume Review
SYSTEM_DESIGN_NOTES.md + Architecture Locked: YES                → resume Engineer
SYSTEM_DESIGN_NOTES.md + no lock                                 → resume Architect
Nothing                                                           → start Architect
```

---

## Setup (every invocation)

1. Read `config.yml` → `project_key`, `max_loops` (default 3), `interactive`
2. Check `memory/features/{slug}/loop_state.json` → loop count + last blocker type
3. Detect state
4. If `<message>`: log as focus hint

---

## ARCHITECT

**Pattern:** Skill orchestrates. Load `.claude/agents/solutions-architect.md` for behavioral constraints. Launches
`codebase-analyst` subagents in parallel for code analysis. `solutions-architect` synthesizes findings into design.

**Gate conditions:**

- `docs/features/{slug}/planning/PRD.md` exists with `PRD Status: APPROVED`
- On loop-back from Review (DESIGN_GAP): read `memory/features/{slug}/open_questions.md` → scope to listed gaps only, do
  not re-run full design

**Step 1: Read inputs (once)**

1. `docs/features/{slug}/planning/PRD.md` — extract: feature scope, NFRs (S5), dependencies (S8), security surface (S7),
   open conflicts (S10), repo list (S12)
2. `docs/features/{slug}/planning/PRD_REVIEW.md` — read if exists: extract conditional items, accepted risks. Skip if
   absent.
3. `docs/features/{slug}/input/confluence/` — prefer `*.md` extracted files. Fall back to `*.json` only if `.md` absent.
   If neither exists and page ID is known, fetch via MCP:
   ```
   mcp__atlassian__confluence_get_page({pageId: "{PAGE-ID}"})
     → python3 scripts/input_extractor.py from-mcp-confluence docs/features/{slug}/input/confluence/{PAGE-ID}.md
   ```
   Title scan only — read if: technical design, architecture, migration plan, API spec, data model. Skip if PRD already
   covers topic.
4. `docs/features/{slug}/input/local-docs/` — same rule: prefer `*.md`, fall back to `*.json`.

Never read: FEATURE_DRAFT.md, DISCOVERY_NOTES.md, input/jira/ — distilled into PRD.

Extract and cache:

- Feature keywords — core technical terms from PRD scope
- NFR targets — specific thresholds from PRD S5
- Security surface — sensitive data, auth requirements
- External dependencies — systems outside codebase
- Blast radius hint — repos/modules PRD explicitly mentions

**Step 2: Launch codebase-analyst subagents** (parallel, max 3, grouped by stack similarity)

Group repos from PRD S12 into max 3 agents. Each agent:

```
Agent: codebase-analyst
Model: haiku
Prompt:
"Respond concisely throughout.
Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths/commands exact. Output capped at 300 words structured summary.

Scan repo: {repo-name} for feature: {feature-keywords}
1. Keyword search → find files/classes matching keywords
2. Per hit: read signatures only (not full impl). Trace imports + public callers max 2 levels.
3. Note existing patterns for similar problems in this repo.
4. Estimate blast radius: files/classes needing change.
5. Return structured summary:
   - Relevant classes (path + purpose)
   - Existing patterns to reuse (file:line)
   - Integration points (what calls what)
   - Blast radius estimate
   - Missing/unclear items (flag, don't assume)
If no keyword hits: return 'no matches — greenfield for this repo'."
```

**Step 3: Launch web-researcher subagent** (only if feature involves external libraries or unfamiliar APIs)

```
Agent: web-researcher
Model: haiku
Prompt:
"Respond concisely throughout.
Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.

Research: {external-lib-or-api} version {version-from-PRD}
Find: version-specific docs, known gotchas, migration notes, rate limits.
Return: direct links with section anchors, key insights, gotchas with mitigations."
```

**Step 4: Merge subagent findings** into context for Step 5 synthesis only. No file written, not persisted beyond this
session.

**Step 5: Architecture synthesis** — `solutions-architect`

Work through in order:

**5a. Interface Contracts** (design first — outside in)

- New/modified API endpoints or event schemas
- Request/response contracts with field types + validation rules
- Error codes per endpoint
- Inline into SYSTEM_DESIGN_NOTES S3 + TDD S3 directly — no separate file

**5b. Pattern Selection**

- Existing pattern found in subagent findings (Step 4) solves this? → use it, document why
- New pattern needed → justify against existing architecture

**5c. Data Flow**

- Step-by-step: client → service → storage for primary use case
- Reference verified class names from subagent findings (Step 4)
- Diagram rule:
    - ≤4 hops, linear → Mermaid `sequenceDiagram` inline
    - > 4 hops OR multiple parallel flows OR complex branching → `/draw {slug} "data flow: {feature-name}"` → saves to
      `docs/features/{slug}/diagrams/`, reference path in SYSTEM_DESIGN_NOTES S4

**5d. Threat Model (STRIDE)**
Per data flow step: Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege. Document
mitigations per threat.

**5e. NFR Validation**
| NFR | Threshold | How Design Meets It | At 10x Load |
|-----|-----------|---------------------|-------------|

**5f. Dependency Map**
| System | SLA | Rate Limit | Failure Mode | Circuit Breaker Threshold |
|--------|-----|-----------|-------------|--------------------------|

**5g. Resilience**
Retry logic, circuit breakers, idempotency per integration point.

**5h. Observability**
Specific metric names, histogram labels, trace span names, alert thresholds.

**5i. Migration/Rollout** (if feature touches existing data/behavior)
Current state → target state. Strategy: dual-write / feature flag / dark launch / canary / big-bang. Rollback trigger +
procedure.

**5j. Targeted Q&A** (if needed — apply AskUserQuestion format below)
Only what code + PRD cannot answer. Max 3 questions. Autonomous mode → auto-decide, log rationale.

For each decision made via Q&A: `TaskCreate({title: "ADR: {decision}", status: "resolved", details: "{rationale}"})`
This persists architectural decisions across turns without relying on context window.

**Step 6: Write SYSTEM_DESIGN_NOTES.md**
Path: `docs/features/{slug}/design/SYSTEM_DESIGN_NOTES.md`

Header:

```
**Technical Owner:** {from PRD}
**AI Co-Author:** Solutions Architect (AI-Generated)
**Date:** {ISO-date}
```

13 sections (all required, N/A + reason if not applicable):

1. **Bounded Context** — verified repos, classes, blast radius, existing patterns (from subagent findings)
2. **Architectural Pattern** — chosen pattern, justification, alternatives rejected
3. **Interface Contracts** — all new/modified endpoints/events with request/response schemas, field types, validation
   rules, error codes
4. **Data Flow** — step-by-step with verified class names + Mermaid diagram
5. **Threat Model** — STRIDE table with mitigations per threat
6. **NFR Validation** — PRD NFR vs design capacity vs 10x load
7. **Dependency Map** — external systems, SLAs, rate limits, failure modes
8. **ADRs** — one per major decision (context, options, decision, rationale). Immutable once written.
9. **Resilience Strategy** — retries, circuit breakers, idempotency per integration point
10. **Observability Plan** — metric names, span names, alert thresholds
11. **Migration/Rollout Strategy** — approach summary (detail in MIGRATION_PLAN.md at Engineer stage)
12. **Remaining Risks** — accepted risks + mitigation plan
13. **Architecture Status** — gate string

Gate string (end of Section 13):

```
Architecture Locked: YES
```

**Gate:** `Architecture Locked: YES` in SYSTEM_DESIGN_NOTES.md → auto-proceed to Engineer.

---

## ENGINEER

**Pattern:** Direct. Load `.claude/agents/tdd-author.md` for behavioral constraints before executing.

**On loop-back entry:** read loop_state.json → check `iteration` against `max_loops`. If exceeded → escalate to human,
stop. Read TDD_REVIEW.md → fix only identified TDD_ISSUE blockers.

**Gate conditions:**

- `Architecture Locked: YES` in SYSTEM_DESIGN_NOTES.md
- PRD.md exists

**Inputs (read once, in order):**

1. `docs/features/{slug}/planning/PRD.md` — requirements, NFRs, ACs
2. `docs/features/{slug}/design/SYSTEM_DESIGN_NOTES.md` — ADRs, data flow, resilience, observability, interface
   contracts (source of truth)

Never read: FEATURE_DRAFT.md, DISCOVERY_NOTES.md, input/, CODE_ANALYSIS.md, API_CONTRACTS.md — all distilled into
SYSTEM_DESIGN_NOTES.

---

### TDD Split Decision

**Decide before writing anything.**

Count repos from SYSTEM_DESIGN_NOTES.md (authoritative). PRD S12 is starting point — Architect may have identified
additional repos during code analysis. SYSTEM_DESIGN_NOTES.md S1 is the final answer.

**Single repo → one file:**

```
design/TDD.md — all 11 sections
```

**Multiple repos → master + per-repo:**

```
design/TDD_MASTER.md        — cross-cutting (sections 1, 2, 8, 9, 10, 11)
design/TDD_{REPO_NAME}.md   — repo-specific (sections 3, 4, 5, 6, 7) per repo
```

Two flows in same repo → one TDD file, separate sections per flow.

**Log split decision:**

```
TDD Split: {single | multi-repo}
Repos: {list}
Files: {list of TDD files to produce}
```

---

### TDD Structure (11 Sections)

All 11 sections must be present. In multi-repo split: S1,2,8,9,10,11 go in TDD_MASTER.md and S3,4,5,6,7 go in each TDD_
{REPO}.md. In single-repo: all 11 sections in TDD.md in order 1-11. Never skip sections — write N/A + reason if not
applicable.

**Cross-cutting** (TDD_MASTER.md for multi-repo, or full TDD.md for single):

1. **Architecture Overview** — pattern, tech stack per repo
    - Always use `/draw {slug} "architecture overview: {feature-name}"` — never Mermaid for architecture. Multi-service
      layouts always need proper spacing. Reference generated file path in TDD S1.
2. **Domain & Module Structure** — bounded contexts, module boundaries, directory tree (feature-driven, not tech-layer)
8. **Vertical Delivery Slices** — 3-5 end-to-end shippable slices. Per slice: PRD user stories, components, ACs,
   dependencies, SP estimate
9. **ADRs** — reproduced from SYSTEM_DESIGN_NOTES verbatim + implementation-level details. Flag `[DESIGN GAP]` if gap
   found.
10. **Resource Requirements** — memory/CPU/storage sized to NFR thresholds
11. **Deployment Architecture** — platform, model (blue-green/rolling/canary), IaC snippet, health checks, rollback

**Repo-specific** (TDD_{REPO}.md for multi-repo, or sections 3-7 in TDD.md for single):

3. **Data Models & Contracts** — SQL DDL, API schemas (implement exactly from SYSTEM_DESIGN_NOTES S3), event schemas,
   config templates
4. **Component Design & Command Lifecycle** — class responsibilities, method signatures (no bodies), sequence diagram
   aligned with SYSTEM_DESIGN_NOTES data flow
    - Diagram rule: ≤4 participants → Mermaid `sequenceDiagram` inline. >4 participants OR complex async flows →
      `/draw {slug} "sequence: {component-name}"` → reference path in TDD S4.
5. **Error Handling & Resilience** — failure taxonomy, exception types, implement SYSTEM_DESIGN_NOTES resilience
   exactly (retry params, circuit breaker thresholds, idempotency keys), security controls per threat model
6. **Observability & Configuration** — implement exact metric names, span names, alert thresholds from
   SYSTEM_DESIGN_NOTES S10. If S10 lacks specific names → flag `[DESIGN GAP]` here, do not invent.
7. **Testing Strategy** — unit/integration/perf/edge tests. Every edge case from PRD + design artifacts → test method (
   Given/When/Then). File locations, fixtures, mocking approach.

**Constraints:**

- No executable code — contracts only
- Every interface traces to PRD. Missing → `[PRD Gap]`
- Honor ADRs — immutable. Disagree → `[DESIGN GAP]`
- Vertical slices by feature, not technology tier
- Complete error taxonomy — all HTTP codes per endpoint, exception types per method

**MIGRATION_PLAN.md (conditional)**
Check SYSTEM_DESIGN_NOTES S11:

- S11 is N/A or contains "no migration required" → skip
- S11 describes an actual migration strategy → write `docs/features/{slug}/design/MIGRATION_PLAN.md`

```markdown
# Migration Plan: {Feature Name}

**Date:** {ISO-date} | **Agent:** solutions-architect (AI-Generated)
**Strategy:** {from SYSTEM_DESIGN_NOTES S11}

## Current State → Target State

## Step-by-Step Migration Sequence

## Rollback Trigger & Procedure

## Validation Checkpoints

## Risk & Contingency
```

**Gate:** All 11 sections present. Slices defined. Interfaces typed. Errors enumerated. → proceed to Review.

---

## REVIEW

**Pattern:** Launch `tdd-reviewer` as isolated subagent. Fresh context — no authorship memory.

**Output artifact:** `docs/features/{slug}/design/TDD_REVIEW.md`

```
Agent: tdd-reviewer
Prompt:
"Respond concisely throughout.
Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths/commands exact.

Review TDD cold — no prior context on this feature.
Read as engineer implementing alone.

Inputs (read once, in order):
1. docs/features/{slug}/design/TDD.md — single repo
   OR TDD_MASTER.md + all TDD_{REPO}.md files found in docs/features/{slug}/design/ — multi-repo
2. docs/features/{slug}/planning/PRD.md
3. docs/features/{slug}/design/SYSTEM_DESIGN_NOTES.md
4. docs/features/{slug}/design/MIGRATION_PLAN.md — read if exists, skip if absent

Execute every checklist item. Record PASS/FAIL/N/A. No item skipped.

A — PRD TRACEABILITY
  A1 Every PRD user story → TDD component or API endpoint
  A2 Every PRD NFR → TDD S10 resource requirements sized accordingly
  A3 Every PRD AC → testable via TDD design
  A4 Every edge case from PRD S4/S5 → TDD S7 test specification
  A5 No over-engineering — no tech not in PRD/design

B — DESIGN COMPLIANCE
  B1 Architectural pattern from SYSTEM_DESIGN_NOTES S2 reflected in TDD S1
  B2 Data flow from SYSTEM_DESIGN_NOTES S4 aligned with TDD S4 sequence diagram
  B3 Resilience strategy from SYSTEM_DESIGN_NOTES S9 implemented exactly in TDD S5
  B4 Observability plan from SYSTEM_DESIGN_NOTES S10 — exact metric/span names in TDD S6
  B5 Threat model mitigations from SYSTEM_DESIGN_NOTES S5 → security controls in TDD S5
  B6 Every ADR from SYSTEM_DESIGN_NOTES S8 reflected in TDD S9 — no contradictions
  B7 Interface contracts from SYSTEM_DESIGN_NOTES S3 implemented exactly in TDD S3

C — ARCHITECTURE STRESS TEST
  C1 N+1 query patterns — missing batch fetching
  C2 APIs lacking pagination — unbounded result sets
  C3 Missing database indexes on query columns
  C4 In-memory structures growing unbounded
  C5 Transactions spanning external calls
  C6 Missing isolation level specifications
  C7 Deadlock potential — lock ordering issues
  C8 Synchronous calls in loops
  C9 Missing connection pooling

D — SECURITY AUDIT
  D1 Missing authorization checks before operations
  D2 Missing multi-tenancy filters where applicable
  D3 PII fields logged or exposed in error messages
  D4 Missing input validation
  D5 Missing rate limiting on public endpoints
  D6 Missing authentication on sensitive operations
  D7 Sensitive data stored unencrypted
  D8 Secrets in config (not in secret manager)
  D9 Missing audit logging for sensitive operations

E — VERTICAL SLICE CRITIQUE
  E1 Each slice end-to-end functional (not horizontal layer)
  E2 Each slice independently deliverable + testable
  E3 Each slice mapped to business value user can see
  E4 No slice depends on another incomplete slice

Severity per finding:
  BLOCKER — contradicts ADR, missing critical section, unfeasible, blocks implementation
  HIGH    — scalability/security gap, incomplete section engineer must guess around
  MEDIUM  — inconsistency, minor gap, defer to implementation acceptable
  LOW     — style, formatting

Blocker type:
  TDD_ISSUE     — TDD writing problem → fix in Engineer stage
  DESIGN_GAP    — architectural decision missing/wrong → loop to Architect stage

Fix MEDIUM/LOW inline in TDD files directly.
BLOCKER/HIGH → record in findings table only, do not fix.

Write TDD_REVIEW.md:
1. Executive Summary — verdict, blocker counts by type, strengths, critical gaps
2. PRD Traceability — per A1-A5 with missing items listed
3. Design Compliance — per B1-B7 (OK / BLOCKER with type)
4. Architecture Stress Test — per C1-C9 findings with section ref + concrete fix
5. Security Audit — per D1-D9 findings with section ref + concrete fix
6. Vertical Slice Critique — per E1-E4 per slice
7. Resolution Plan — blockers, high priority, acceptable risks, verdict

Verdict:
  APPROVED    — 0 BLOCKERs, 0 HIGHs
  CONDITIONAL — 0 BLOCKERs, HIGHs present (proceed after fixing HIGHs)
  REJECTED    — any BLOCKER present"
```

**On subagent return:**

If APPROVED or CONDITIONAL:

1. Update loop_state: `{"design": {"iteration": N, "status": "PASS"}}`
2. CONDITIONAL → log HIGH findings as tech debt, do not block progression
3. Proceed to `/breakdown {slug}`

If REJECTED:

1. Read current loop_state → get existing iteration count
2. Write:
   `{"design": {"iteration": previous+1, "last_blocker_type": "TDD_ISSUE|DESIGN_GAP", "findings": [...], "timestamp": "ISO"}}`
3. Check `iteration` against `max_loops` — if exceeded → escalate to human, stop
4. Any `DESIGN_GAP` → write to `memory/features/{slug}/open_questions.md`, return to Architect
5. All `TDD_ISSUE` → return to Engineer
6. Mixed → Architect first, then Engineer

---

## AskUserQuestion Format

Load: `ToolSearch → query: "select:AskUserQuestion"`

### Decision Rule

Ask only if:

- Two valid options exist with real trade-offs + no clear winner from code/PRD/SYSTEM_DESIGN_NOTES
- A class/file is missing that materially affects the design (flag as risk question)
- An NFR cannot be met by any obvious approach (escalate as P0)

Never ask:

- Anything answerable from PRD, SYSTEM_DESIGN_NOTES, or subagent findings
- Generic architecture questions ("how should we handle errors?", "which pattern?")
- Questions where one option is clearly better given codebase evidence

Autonomous mode (`interactive: false`): auto-select best option, log rationale, never ask.

### Question Format

One question at a time. Acknowledge each answer before next question.

```
AskUserQuestion({
  "questions": [{
    "header": "Label (12 chars)",
    "question": "Q{n} [{category}] [{priority}]: {Specific question with full context.}\n\nWhy this matters: {impact on architecture/TDD/implementation if wrong}\n\nFound: {what code/PRD shows — cite file:line or PRD section}",
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
        "description": "Document as risk in SYSTEM_DESIGN_NOTES S12. Unblocks progress."
      }
    ]
  }]
})
```

**Priority tags:**

- `P0` — blocks architecture lock. Must resolve before SYSTEM_DESIGN_NOTES gate.
- `P1` — important. Resolve before TDD authoring.
- `P2` — nice-to-know. Can defer to TDD or implementation.

**Category tags:**
`Architecture` · `Data Model` · `Integration` · `Performance` · `Security` · `Resilience` · `Migration` ·`Observability`

### After Each Answer

```
✅ Q{n}: {summary of answer chosen}
{If follow-up needed}: Q{n+1} builds on this — {why}
```

Adaptive follow-ups: use previous answers to shape next question. If user chose event-driven → ask about event schema.
If user chose sync → skip queue/retry questions.

### User Navigation Commands

Respond to these at any point during Q&A:

- `progress` → show Q{done}/{total}, list resolved answers so far
- `summary` → show all answers recorded so far
- `skip` → mark current question P2, move to next
- `back` → revisit previous question, update answer
- `stop` → halt Q&A, record remaining as risk in SYSTEM_DESIGN_NOTES S12

### Multiselect (when applicable)

Use `"multiSelect": true` only when multiple options genuinely coexist (e.g. "which failure modes apply?"). Never use
for mutually exclusive architectural decisions.

---

## Loop State

Path: `memory/features/{slug}/loop_state.json`

```json
{
  "planning": {
    "iteration": 1,
    "status": "PASS"
  },
  "design": {
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
Design complete: {slug}
Working files retained.

Architect: SYSTEM_DESIGN_NOTES.md — Architecture Locked: YES ({N} ADRs)
Engineer:  {TDD.md | TDD_MASTER.md + {N} repo TDDs} — {N} slices
           MIGRATION_PLAN.md — {present | skipped}
Review:    TDD_REVIEW.md — {APPROVED | CONDITIONAL}
Iterations: {N}

Next: /breakdown {slug}
```

---

## Prerequisites

- `docs/features/{slug}/planning/PRD.md` with `PRD Status: APPROVED`
- `config.yml` at repo root
