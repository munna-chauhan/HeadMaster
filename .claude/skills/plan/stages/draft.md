# DRAFT

**Pattern:** Direct. Load `.claude/agents/prd-author.md`.

**On loop-back:** read `loop_state.json` → fix flagged sections only. Convergence already validated.

**On message (unapproved PRD):** `/plan slug message` with PRD.md existing but not APPROVED:
1. Parse intent from message — classify as: section feedback, missing content, scope correction, or general comment.
2. Edit affected PRD sections directly.
3. Resume Review stage (PRD was already drafted, message is a refinement).

**Revision mode** (`pipeline.revision_open = true`): check → read Planning section in `REVISION_NOTES.md` → edit PRD delta only (no re-draft) → append decisions back to Planning section before gate.

**Pre-conditions (tier-aware):**
- xs: FEATURE_DRAFT.md or IMPLEMENTATION_BRIEF.md exists (no discovery required)
- s: FEATURE_DRAFT.md exists + ends with `All Gaps Resolved: YES`
- m/l: FEATURE_DRAFT.md exists + DISCOVERY_NOTES.md ends with `All Questions Resolved: YES`

Missing → halt, return to Init/Discover.

**Inputs (read once, tier-aware):**
- xs/s: FEATURE_DRAFT.md → `input/*.md` (no DISCOVERY_NOTES.md)
- m/l: FEATURE_DRAFT.md → DISCOVERY_NOTES.md → `input/*.md`

Prefer `.md` over `.json` for input files.

**Write** `docs/features/{project}/{slug}/planning/PRD.md`

Header: standard PRD header table from SKILL.md (Status: Draft).

**Sections:**

Read `stages.prd.sections` from `.claude/workflows/{tier}.yml` as TEMPLATE/GUIDANCE (not enforcement).

prd-author decides sections based on DISCOVERY_NOTES.md content. Use tier template as starting point, adjust based on what content requires.

**Rules:**
- **Single source of truth:** PRD must be self-contained. No cross-references to FEATURE_DRAFT, DISCOVERY_NOTES, or input files in body.
- No omissions (N/A + reason if empty)
- No source annotations ('per Jira', 'as discussed in Confluence', 'see FEATURE_DRAFT')
- All technical terms defined in Glossary or inline
- Diagrams only when clearer than prose:

| Type           | When                       | Tool                                    |
|----------------|----------------------------|-----------------------------------------|
| User/process   | >3 steps with branches     | Mermaid (simple) or `/draw` (complex)   |
| System context | services + external actors | `/draw`                                 |
| Gantt/phasing  | 3+ phases                  | Mermaid `gantt`                         |
| State machine  | status transitions         | Mermaid (simple) or `/draw` (many)      |

Mermaid inline ≤5 nodes only. Never for architecture diagrams.

**NO_PRIOR_KNOWLEDGE_TEST (m/l tiers only):** Could an unfamiliar engineer implement from PRD alone? If no → add context.
For s tier: assume reader knows the codebase; PRD must still be self-contained but can reference established patterns by name without full explanation.

**Gate:** All necessary sections present, metrics quantified, self-contained.

```bash
sh scripts/gate_transition.py {project} {slug} planning Review --artifact docs/features/{project}/{slug}/planning/PRD.md
sh scripts/gate_transition.py {project} {slug} plan-stage draft complete
```

**Stop.** Print:
```
PRD written → docs/features/{project}/{slug}/planning/PRD.md
Start a new session: /plan {slug} to review.
```
Do not proceed to Review in this session.
