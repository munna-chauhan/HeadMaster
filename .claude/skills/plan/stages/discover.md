# DISCOVER

**Pattern:** Direct (inline). All tiers. Interactive Q&A agents must run inline — subagent execution breaks AskUserQuestion tool calls.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

---

## Source Detection (all tiers except xs)

**deep_analysis:** true if (tier = m or l) AND any of:
- `input/jira/` has .md files
- `input/confluence/` has .md files
- `input/local-docs/` has .md files

Otherwise: false (sequential path).

---

## Routing

```bash
sh scripts/workflow_config.py {tier} stages discovery status
```
- `skip` → HALT
- `optional` → check gaps: ≤2 skip, 3-5 ask user, 6+ run
- `required` → always run

---

## Depth by tier

| Tier | Questions | Output artifact |
|------|-----------|----------------|
| xs   | skip      | —              |
| s    | 3-5       | FEATURE_DRAFT.md (inline) |
| m    | 5-8       | DISCOVERY_NOTES.md |
| l    | 8-12      | DISCOVERY_NOTES.md |

---

## Prior Work Check (all tiers except xs)

Before Q&A: check each target repo for branches matching feature keywords.

```bash
git -C {repo-root} branch -a | grep -i "{feature-keywords}"
```

If branch found:
- Read up to 3 test files + 1 config/wiring file from that branch
- Treat discovered tests as resolved requirements → `[Assumption: matches branch {branch-name}]` (P2)
- Treat discovered config as convention baseline — reference in Analysis findings
- Append findings before Q&A phase; do not re-ask what the branch already answers

If no branch found → proceed.

---

## Question priority

| Priority | Criteria | Action |
|----------|----------|--------|
| P0 | Missing business rule, undefined core behavior | AskUserQuestion — blocks Draft |
| P1 | Affects ≥2 PRD sections OR changes critical path OR adds ≥3 SP | AskUserQuestion or code research |
| P2 | Single section impact | `[Assumption: ...]` — document, do not escalate |

P1 also covers: external system change not in original scope → AskUserQuestion.

**Never auto-resolve** security, observability, or metrics gaps — these are deferred to the Review optional gate. Mark as `[DEFERRED: handled in Review]`.

One question at a time. Never ask what inputs already answer.

**Minimum category coverage** — before ending discovery, verify at least one question from each applicable category was asked or explicitly ruled out:

| Category | Applicable when | Minimum question if not in inputs |
|---|---|---|
| Biz Rules | Always | "What are the exact conditions that trigger / complete this feature?" |
| Edge Cases | Always | "What happens if a dependency is unavailable? What's the data limit and what happens at limit+1?" |
| Integration | Any external system mentioned | "What is the API contract / auth mechanism for {system}? Are there downstream consumers?" |
| Performance | SLA or load mentioned | "What is the expected request volume and acceptable response time?" |
| UX | User-facing flow | "What does the user see on success and on failure?" |

If a category has no applicable gaps → mark `[N/A: {reason}]`, do not ask.

---

## s tier — inline resolution

1. Read FEATURE_DRAFT.md Sections 6 (Gaps) and 7 (Questions)
2. P0/P1 → AskUserQuestion; P2 → `[Assumption: ...]`
3. Mark each gap `[RESOLVED: {answer or assumption}]` in FEATURE_DRAFT.md
4. Append: `All Gaps Resolved: YES`

Gate:
```bash
sh scripts/gate_transition.py {project} {slug} planning Draft --artifact docs/features/{project}/{slug}/planning/FEATURE_DRAFT.md
sh scripts/gate_transition.py {project} {slug} plan-stage discover complete
```

---

## m/l tier — Continuous Brain Dump (DISCOVERY_NOTES.md)

DISCOVERY_NOTES.md is a working journal, append-only per phase. TDD author reads it to understand discovery journey. If session ends, re-enter at current phase marker — no re-run needed.

**Phase markers (one per section):**
- `[COMPLETE: YYYY-MM-DD]` — phase done, skip on re-run
- `[IN_PROGRESS]` — current phase
- `[PENDING]` — not yet started

**File structure:**
```
## Analysis Phase [IN_PROGRESS]
(findings from sources or sequential read — append only)

## Q&A Phase [PENDING]
(questions and answers — append only)

## Plan Mode Discussion [PENDING]
(if entered — discussion and synthesis — append only)

---
All Questions Resolved: YES (append at very end when complete)
```

**Execution:**

1. Check if `docs/features/{project}/{slug}/planning/DISCOVERY_NOTES.md` exists:
   - If exists: read phase markers, resume at current phase
   - If not: create with `## Analysis Phase [IN_PROGRESS]`

2. **Analysis Phase:**
   - If deep_analysis: true → EnterPlanMode → launch parallel Explore agents per source → synthesize FALSE/REAL gaps → ExitPlanMode → append findings
   - If deep_analysis: false → sequential read FEATURE_DRAFT + sources → append findings
   - Identify gaps. If clear, mark `[Analysis Phase] [COMPLETE]` and skip Plan Mode.

3. **During analysis, if doubts arise:**
   - Ask clarifying questions inline (AskUserQuestion)
   - Append Q&A to Analysis Phase section

4. **If major uncertainty remains after analysis:**
   - EnterPlanMode → discuss findings with user → ExitPlanMode
   - Update `[Analysis Phase]` marker to `[COMPLETE]`
   - Create `[Plan Mode Discussion]` section, append discussion/synthesis

5. **Q&A Phase (if gaps remain):**
   - Load `.claude/agents/requirements-analyst.md`
   - Spawn requirements-analyst (inline) with identified REAL GAPS
   - Agent uses AskUserQuestion for P0/P1/P2 gaps (one at a time)
   - Agent verifies category coverage (Biz Rules, Edge Cases, Integration, Performance, UX)
   - Append Q&A results to Q&A Phase section
   - Mark `[Q&A Phase] [COMPLETE]`

6. **Finalize:**
   - Update all phase markers to `[COMPLETE]` if not already
   - Append: `All Questions Resolved: YES`

Gate:
```bash
sh scripts/gate_transition.py {project} {slug} planning Draft --artifact docs/features/{project}/{slug}/planning/DISCOVERY_NOTES.md
sh scripts/gate_transition.py {project} {slug} plan-stage discover complete
```
