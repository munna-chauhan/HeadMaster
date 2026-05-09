# ARCHITECT

**Agents:** `solutions-architect`, `codebase-analyst` (subagent, parallel), `web-researcher` (subagent, conditional)

**Pattern:** Skill orchestrates. Spawn codebase-analyst subagents in parallel.

**Gate conditions:**

| Condition | Action |
|-----------|--------|
| `artifacts["planning/PRD.md"].status = approved` | proceed |
| `complexity_tier = xs` | skip stage → Engineer |
| Loop-back from Review (DESIGN_GAP) | read `memory/features/{project}/{slug}/open_questions.md` → scope to listed gaps only |
| `pipeline.revision_open = true` | run `python scripts/revision_manager.py check {project} {slug} design` → read REVISION_NOTES.md Design section → delta-only edits → append decisions before gate |

---

## Must-Rules (apply every invocation)

### Reuse Audit (run BEFORE proposing any new component)
For every proposed class, interface, layer, or component:
1. Glob the name and synonyms in target + reference repos.
2. Read existing implementations if found. Mirror surface; justify deviations.
3. Document in SYSTEM_DESIGN_NOTES.md as a Reuse Audit table: `component | exists? | action (reuse/mirror/extend/new)`. Net-new must be a finding, not an assumption.
4. Rule delivered to solutions-architect via `memory/agents/solutions-architect/MEMORY.md`.

### Read-Whole on shared docs (>500 lines)
Reference docs longer than 500 lines: read in full or via index-then-targeted reads covering every named section. Master Index present → read it first, then load every sub-section the current task touches.

### Generic substitution preferred over field addition + workaround
When an existing class is parameterized on `T`, substitute `T` — do not add a sibling field + injection workaround. Check parent-class parameterization before proposing any new injection mechanism. Detail: `memory/agents/tdd-author/MEMORY.md` "Generic substitution preferred over field addition + workaround".

---

## Steps

**1. Read inputs (once)**

| # | Path | Extract |
|---|------|---------|
| 1 | `docs/features/{project}/{slug}/planning/PRD.md` | scope, NFRs, dependencies, security surface, repo list |
| 2 | `docs/features/{project}/{slug}/input/confluence/*.md` | prefer `.md` over `.json`; fetch via MCP if absent |
| 4 | `docs/features/{project}/{slug}/input/local-docs/*.md` | prefer `.md` over `.json` |

Never read: `FEATURE_DRAFT.md`, `DISCOVERY_NOTES.md`, `PRD_REVIEW.md`, `input/jira/` — distilled into PRD.

Cache: feature keywords, NFR targets, security surface, external dependencies, blast radius hint.

**2. Launch codebase-analyst subagents** (parallel, max 3, grouped by stack)

Spawn all in a single message (multiple Agent tool calls). Do NOT spawn sequentially.

Focus: architectural patterns, integration points, blast radius.
Return: structured summary — relevant classes (path+purpose), reuse patterns (file:line), integration points, blast radius estimate, unclear items. Signatures + call chains (2 levels max). 300-word cap per repo.

```
Agent: codebase-analyst
Model: claude-haiku-4-5-20251001
Prompt:
"Execute per .claude/agents/codebase-analyst.md definition.

Context: Design phase architecture analysis
Repo: {repo-name}
Feature keywords: {feature-keywords}

Return structured summary (not Q&A):
  * Relevant classes (path + purpose)
  * Existing patterns to reuse (file:line)
  * Integration points
  * Blast radius estimate
  * Missing/unclear items (flag, don't assume)

Output cap: 300 words. If no matches: return 'no matches — greenfield for this repo'."
```

**3. Launch web-researcher subagent** (only if PRD has external libraries with specific versions)

Focus: integration patterns, known issues, rate limits for architectural decisions.
Return: YAML per agent definition. 300-word cap (tables/code exempt).

```
Agent: web-researcher
Model: sonnet
Prompt:
"Execute per .claude/agents/web-researcher.md definition.

Context: Design phase architecture analysis
Library: {library-name}
Version: {version-from-PRD}
Project stack: {from PRD Repos section}

Focus:
- Integration patterns for this stack
- Known issues affecting architecture (rate limits, connection pooling, retry logic)
- Security advisories affecting design
- Return YAML format per agent definition

Output cap: 300 words (tables/code exempt)."
```

**4. Blind Comparison Architecture Evaluation**

**4a — Produce 3 proposals (one pass)** from merged subagent findings + PRD:

| Profile | Focus |
|---------|-------|
| A — Performance | Maximize throughput, latency, scalability. Accept higher complexity. |
| B — Maintainability | Maximize team velocity and long-term health. Accept some performance tradeoff. |
| C — Simplicity | Minimize moving parts and abstraction layers. Fewest components. |

Each proposal: 5–8 bullets covering data flow, component boundaries, key tech choices, main risk.

**4b — Architecture evaluation + design (solutions-architect)**

Load `.claude/agents/solutions-architect.md`.

Agent receives: PRD.md, tier (s/m/l), merged subagent findings, 3 proposals (X/Y/Z) + NFRs + security surface. Evaluates per Proposal Evaluation in agent definition.

Interactive mode (from `gates.design.interactive` in config.yml):

| Value | Behavior |
|-------|----------|
| `true` | Agent may use AskUserQuestion for ambiguities |
| `false` + autonomous | Auto-decides, logs rationale to run-log.md |
| `false` + supervised | Asks only for critical gaps |

Agent produces: full SYSTEM_DESIGN_NOTES.md per `.claude/agents/references/system-design-notes.structure.md`, gate string `Architecture Locked: YES`.

**5. Validate artifact**

| Check | Detail |
|-------|--------|
| File exists | `docs/features/{project}/{slug}/design/SYSTEM_DESIGN_NOTES.md` |
| Gate string | Last 200 bytes contain `Architecture Locked: YES` |
| Section count | `## ` headers = 13 |
| Header table | Present in first 500 bytes |

On failure: retry solutions-architect once with `"SYSTEM_DESIGN_NOTES.md incomplete: {what's missing}"`. Second failure → escalate to human.

**6. Gate transition**

```bash
python scripts/gate_transition.py {project} {slug} artifact "design/SYSTEM_DESIGN_NOTES.md" locked
python scripts/gate_transition.py {project} {slug} design Engineer
```

Auto-proceed to Engineer stage.
