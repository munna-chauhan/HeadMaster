---
name: handoff
description: Save compressed session state to memory then auto-run /clear. Max 100 lines output.
---

# /handoff

Save state → clear context. Session continues clean. Artifacts + memory persist.

## Output limit

**Hard limit: 100 lines, compressed format only.**
Drop articles, filler, full sentences. Fragments + bullets only.
No conversation recap. Technical state only.

---

## Step 1: Gather state

```
git branch --show-current
git log --oneline -3
git diff --stat HEAD
```

## Step 2: Write handoff file

**Path:** `memory/features/{project}/{slug}/session-{YYYYMMDD-HHMMSS}.md`

**Template (stay under 100 lines):**

```markdown
# Handoff: {slug} {YYYYMMDD-HHMM}

Phase: {planning|design|breakdown|execute} | Stage: {stage}
Branch: {branch} | Story: {STORY-KEY or —}

## Done
- {task}: {file or result}

## Next
- **{exact next step}**: {file:line or command}

## Blockers
- {blocker or None}

## Decisions
- {decision}: {rationale one line}

## Dead ends
- {approach}: {why failed}

## Files changed
- {file}: {one-line purpose}

## Health
Build: {PASS|FAIL} | Tests: {N/N} | Branch: {clean|dirty}

## Resume
cd {repo} && git checkout {branch}
{exact next command}
```

> `Phase:` tag is required — `feature_context.py` uses it to inject only phase-relevant handoffs into new sessions.

## Step 3: Cleanup old sessions

```
memory/features/{project}/{slug}/session-{ts}.md
```

Keeps last 10 session files. Deletes older ones.

## Step 4: Confirm + clear

Print:
```
Handoff saved: memory/features/{project}/{slug}/session-{ts}.md
Clearing context...
```

Then run `/clear`.
