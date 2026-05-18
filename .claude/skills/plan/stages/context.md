# CONTEXT

**Pattern:** Skill orchestrates + `codebase-analyst` subagent (conditional).

**Does:** Read all raw input, fetch external data (Jira/Confluence), scan codebase (if tier requires), write FEATURE_DRAFT.md.
**Assumes:** `/init-feature` completed. `plan/SKILL.md` already verified gate + pipeline mode before loading this stage. FEATURE_INPUT.md and any user-shared local docs are already in `input/`.

---

## Step 1: Read all inputs

**Directory:** `docs/features/{project}/{slug}/input/`

**Read:**
- `FEATURE_INPUT.md` (required — placed by `/init-feature`)
  - If missing → HALT: "FEATURE_INPUT.md not found. Run /init-feature first."
- `USER_CONTEXT.md` (optional — created when `/plan slug message` is invoked on fresh start)
  - Contains user's seed message: requirements, clarifications, intent.
  - Merge with FEATURE_INPUT.md — user context supplements, does not replace.
- `local-docs/*.md` (optional — copied by `/init-feature`)
  - User-shared docs: existing TDDs, specs, analysis reports, architecture notes, etc.
  - If empty → fine, proceed with FEATURE_INPUT.md only.

**Extract from FEATURE_INPUT.md:**
- Feature name, business goal, description
- External refs (Jira tickets, Confluence pages) — needed for Step 2
- Codebases affected
- Known constraints
- Open questions (if pre-filled)

**Extract from local-docs (if present):**
- Additional context, design decisions, prior analysis
- Contradictions or gaps vs FEATURE_INPUT.md

---

## Step 2: Fetch external data (conditional)

**Condition:** FEATURE_INPUT.md Section 3 (External References) has Jira/Confluence links.
- No refs → skip, proceed to Step 3.
- Has refs → fetch below.

**Fetch order:**
1. MCP tools (preferred):
   - Jira: `sh scripts/input_extractor.py -q from-mcp-jira -o docs/features/{project}/{slug}/input/{KEY}.md`
   - Confluence: `sh scripts/input_extractor.py -q from-mcp-confluence -o docs/features/{project}/{slug}/input/{page-slug}.md`
2. Fallback: `/jira-ops fetch` → `.md`
3. Batch extract any remaining JSON: `sh scripts/input_extractor.py -q dir -i docs/features/{project}/{slug}/input/`

**Output:** Extracted `.md` files saved to `input/` alongside FEATURE_INPUT.md.

**On fetch failure:** Log warning, continue with available inputs. Do not block.

---

## Step 3: Codebase scan (conditional)

**Condition:** Read workflow file from loop_state.json → `workflow` field.
- If `workflow = research` → read `.claude/workflows/research.yml`
- Otherwise → read `.claude/workflows/{tier}.yml`

| Workflow / Tier | Scan |
|-----------------|------|
| research (spike) | deep |
| xs | skip |
| s  | skip |
| m  | shallow |
| l  | shallow |

- `skip` (xs/s) → proceed to Step 4 using input files only.
- `shallow` (m/l) → spawn codebase-analyst with shallow prompt.
- `deep` (research) → spawn codebase-analyst with deep prompt.

**ISOLATION:** Do NOT load FEATURE_INPUT.md or external data into parent context before spawning.

### Shallow scan (m/l tiers)

```
Agent: codebase-analyst | Model: haiku
Prompt:
"Execute per .claude/agents/codebase-analyst.md definition.
Feature: {name} | Repos: {list}
Read: docs/features/{project}/{slug}/input/FEATURE_INPUT.md

Answer (table format, 300-word cap):
1. Where does feature live? (module, package, dir)
2. Related code? (file:line, max 10)
3. Patterns to follow? (naming, structure, frameworks)
4. Data entities? (tables, models, schemas)
5. Constraints? (API contracts, config)"
```

### Deep scan (research/spike)

```
Agent: codebase-analyst | Model: sonnet
Prompt:
"Execute per .claude/agents/codebase-analyst.md definition.
Feature: {name} | Repos: {list}
Research questions: {from loop_state.json}
Read: docs/features/{project}/{slug}/input/FEATURE_INPUT.md + input/local-docs/

Analyze per repo (max 20 files, 3 levels deep, 1500-word cap):
1. Entry points, module structure, key abstractions
2. Data flow — end-to-end trace
3. Dependencies — internal/external, version constraints
4. Patterns — architecture, naming, config conventions
5. Risk areas — complexity, coupling, tech debt
6. Research questions — answer each with file:line evidence"
```

---

## Step 4: Write FEATURE_DRAFT.md

**Location:** `docs/features/{project}/{slug}/planning/FEATURE_DRAFT.md`

**Merge sources:**
- FEATURE_INPUT.md (always — primary source)
- Local docs from `input/local-docs/` (if present)
- Fetched external data from `input/` (if fetched in Step 2)
- Codebase scan findings (if run in Step 3) → sections 3-5

### Frontmatter

```yaml
---
feature: { slug: , name: , route: spike|hotfix|feature|epic, owner: , created: ISO-date }
jira: { epic_key: KEY or null }
status: { stage: Context, last_updated: ISO-date }
---
```

### Header

Standard table format `| Field | Value |` with:
- Technical Owner*, Date*, Complexity Tier, AI Co-Author, Feature Folder

### Sections (8)

| # | Section | xs/s (no scan) | m/l (with scan) |
|---|---------|----------------|-----------------|
| 1 | Goal | FEATURE_INPUT.md | FEATURE_INPUT.md |
| 2 | Data Sources | List inputs used | List inputs used |
| 3 | System Context | FEATURE_INPUT.md repos | codebase-analyst Q1-Q3 |
| 4 | Data Model | "TBD — pending /design" | codebase-analyst Q4 |
| 5 | Conflicts | FEATURE_INPUT.md constraints | codebase-analyst Q5 + constraints |
| 6 | Gaps (min 3 for m/l, 1 for s) | input + local-docs analysis | input + local-docs + scan delta |
| 7 | Questions (min 2 for m/l, 1 for s) | carry forward + new, tagged P0/P1/P2 | carry forward + scan-derived |
| 8 | Repos | `repo-registry.yml` if exists, else FEATURE_INPUT.md | `repo-registry.yml` + scan confirmation |

---

## Step 5: Gate transition

```bash
sh scripts/gate_transition.py {project} {slug} planning Context --artifact docs/features/{project}/{slug}/planning/FEATURE_DRAFT.md
sh scripts/gate_transition.py {project} {slug} plan-stage context complete
```

**Gate criteria (tier-aware):**

| Tier | Gaps min | Questions min | Notes |
|------|----------|---------------|-------|
| xs   | 0        | 0             | Feature draft is optional; if produced, no minimums enforced |
| s    | 1        | 1             | Lightweight — just enough to seed PRD |
| m    | 3        | 2             | Standard threshold |
| l    | 3        | 2             | Standard threshold |

FEATURE_DRAFT.md exists + tier minimums met → advance to Discover.
