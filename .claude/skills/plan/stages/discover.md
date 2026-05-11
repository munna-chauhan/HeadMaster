# DISCOVER

**Pattern:** Direct (inline). All tiers. Interactive Q&A agents must run inline — subagent execution breaks AskUserQuestion tool calls.

All AskUserQuestion calls → per `.claude/agents/references/ask-user-protocol.md`.

---

## Routing

```bash
python scripts/workflow_config.py {tier} stages discovery status
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
python scripts/gate_transition.py {project} {slug} planning Draft --artifact docs/features/{project}/{slug}/planning/FEATURE_DRAFT.md
python scripts/gate_transition.py {project} {slug} plan-stage discover complete
```

---

## m/l tier — DISCOVERY_NOTES.md

Load `.claude/agents/requirements-analyst.md`. Run discovery per agent definition.

Output: `docs/features/{project}/{slug}/planning/DISCOVERY_NOTES.md`

Format:
```
### Q{N}: {question}
**Category:** Business Rules | UX | Edge Cases | Integration | Performance
**Answer:** {answer}
**Source:** user | codebase:file:line | jira:KEY | confluence:page
```

End with: `All Questions Resolved: YES`

Gate:
```bash
python scripts/gate_transition.py {project} {slug} planning Draft --artifact docs/features/{project}/{slug}/planning/DISCOVERY_NOTES.md
python scripts/gate_transition.py {project} {slug} plan-stage discover complete
```
