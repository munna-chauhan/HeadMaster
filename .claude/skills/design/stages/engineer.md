# ENGINEER

**Agents:** `tdd-author`

**Pattern:** Direct. Load `.claude/agents/tdd-author.md` for behavioral constraints.

**On loop-back:** convergence already validated by `convergence_check.py`. Read `blocker_history` → fix only current findings from TDD_REVIEW.md.

**Interactive mode** (from `gates.design.interactive` in config.yml):

| Value | Behavior |
|-------|----------|
| `true` | AskUserQuestion for ambiguities |
| `false` + autonomous | Auto-decides, logs to run-log.md |
| `false` + supervised | Asks only critical gaps |

**Gate conditions:**

| Tier | Required |
|------|----------|
| xs | PRD.md exists |
| s/m/l | PRD.md exists + `Architecture Locked: YES` in SYSTEM_DESIGN_NOTES.md |

**Inputs (read once):**
1. `docs/features/{project}/{slug}/planning/PRD.md` — requirements, NFRs, ACs
2. `docs/features/{project}/{slug}/design/SYSTEM_DESIGN_NOTES.md` — source of truth (skip for xs)

**External references:** TDD files MAY reference child TDD_{REPO}.md (multi-repo) and MIGRATION_PLAN.md. MUST NOT reference SYSTEM_DESIGN_NOTES.md, API_CONTRACTS.md, CODE_ANALYSIS.md, input/, FEATURE_DRAFT.md, DISCOVERY_NOTES.md, PRD_REVIEW.md, or planning artifacts. TDD must be self-contained.

---

## TDD Split Decision

| Tier | Artifact | Split? |
|------|----------|--------|
| xs | IMPLEMENTATION_BRIEF.md (5 sections) | Never |
| s/m/l, single repo, <1000 lines | TDD.md | No |
| s/m/l, multi-repo OR >1000 lines | TDD_MASTER.md + TDD_{NAME}.md | Yes |

**When splitting:**
- TDD_MASTER.md: cross-cutting architecture (sections 1, 2, 8, 9, 10, 11*)
- TDD_{REPO|MODULE}.md: component-specific (sections 3, 4, 5, 6, 7)
- *Section count per tier from `.claude/workflows/{tier}.yml`

---

## TDD Header

Load template from: `.claude/skills/design/references/tdd-header.md`

---

## Section Counts

Read `stages.tdd.sections` from `.claude/workflows/{tier}.yml`.

| Tier | Sections | Artifact |
|------|----------|----------|
| xs | 5 | IMPLEMENTATION_BRIEF.md |
| s | 8 | TDD.md |
| m | 10 | TDD.md |
| l | 11 | TDD.md |

**m/l constraints:** No executable code — contracts only. Every interface traces to PRD (missing → `[PRD Gap]`). Honor ADRs — immutable (disagree → `[DESIGN GAP]`). Vertical slices by feature, not technology. Complete error taxonomy per endpoint.

**m/l MIGRATION_PLAN.md:** Check SYSTEM_DESIGN_NOTES S11 — if migration strategy present → write `docs/features/{project}/{slug}/design/MIGRATION_PLAN.md`.

**Forbidden:** No "Completion Summary", "Version History", "Changelog" sections, and no sections beyond the tier-specified count.

---

## Validation (before proceeding)

All tiers share the same validation logic:

1. All tier-required sections present
2. Each section has ≥5 lines of content (excluding headings/blank lines)
3. m/l additionally: vertical slices defined, interfaces typed, error taxonomy complete, resources sized (m/l), deployment documented (l)

**On failure:** do NOT proceed. Return to TDD writing with: `"{ARTIFACT} incomplete — Section {N} ({name}) missing or <5 lines."`

**On pass:**

| Tier | Action |
|------|--------|
| xs | Append `<!-- completeness-check: PASSED {ISO-date} -->`, gate_transition to APPROVED, skip Review → breakdown |
| s/m/l | gate_transition artifact to `draft`, proceed to Review |

```bash
# xs:
python scripts/gate_transition.py {project} {slug} artifact "design/IMPLEMENTATION_BRIEF.md" approved
python scripts/gate_transition.py {project} {slug} design APPROVED

# s/m/l (single):
python scripts/gate_transition.py {project} {slug} artifact "design/TDD.md" draft
# s/m/l (multi — run per file):
python scripts/gate_transition.py {project} {slug} artifact "design/TDD_MASTER.md" draft
python scripts/gate_transition.py {project} {slug} artifact "design/TDD_{NAME}.md" draft
```
