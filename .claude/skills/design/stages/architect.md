# ARCHITECT

**Pattern:** Skill orchestrates. Load `.claude/agents/solutions-architect.md` for behavioral constraints. Launches
`codebase-analyst` subagents in parallel for code analysis. `solutions-architect` synthesizes findings into design.

**Gate conditions:**

- `docs/features/{slug}/planning/PRD.md` exists with `PRD Status: APPROVED`
- On loop-back from Review (DESIGN_GAP): read `memory/features/{slug}/open_questions.md` → scope to listed gaps only, do
  not re-run full design

**Step 1: Read inputs (once)**

1. `docs/features/{slug}/planning/PRD.md` — extract: feature scope, NFRs, dependencies, security surface,
   open conflicts, repo list (from Repos section if full tier, or from Dependencies/FRs for standard tier)
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

Group repos from PRD (Repos section or Dependencies section) into max 3 agents. Each agent:

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
    - >4 hops OR multiple parallel flows OR complex branching → `/draw {slug} "data flow: {feature-name}"` → saves to
      `docs/features/{slug}/diagrams/`, reference path in SYSTEM_DESIGN_NOTES S4

**5d. Threat Model (STRIDE)**
Per data flow step: Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege. Document
mitigations per threat.

**5e. NFR Validation**
| NFR | Threshold | How Design Meets It | At 10x Load |

**5f. Dependency Map**
| System | SLA | Rate Limit | Failure Mode | Circuit Breaker Threshold |

**5g. Resilience**
Retry logic, circuit breakers, idempotency per integration point.

**5h. Observability**
Specific metric names, histogram labels, trace span names, alert thresholds.

**5i. Migration/Rollout** (if feature touches existing data/behavior)
Current state → target state. Strategy: dual-write / feature flag / dark launch / canary / big-bang. Rollback trigger +
procedure.

**5j. Targeted Q&A** (if needed — apply AskUserQuestion format)
Only what code + PRD cannot answer. Max 3 questions. Autonomous mode → auto-decide, log rationale.

For each decision made via Q&A: `TaskCreate({title: "ADR: {decision}", status: "resolved", details: "{rationale}"})`

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
3. **Interface Contracts** — all new/modified endpoints/events with request/response schemas, field types, validation rules, error codes
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

Gate string (end of Section 13): `Architecture Locked: YES`

**Gate:** `Architecture Locked: YES` in SYSTEM_DESIGN_NOTES.md → update pipeline state + auto-proceed to Engineer.

```bash
python3 scripts/gate_transition.py {slug} design Engineer --artifact docs/features/{slug}/design/SYSTEM_DESIGN_NOTES.md
```
