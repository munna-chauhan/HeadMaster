---
name: handoff
type: command
description: Save compressed session state to memory then auto-run /clear. Max 100 lines output.
---

# Handoff

Save state → clear context. Session continues clean. Artifacts + memory persist.

## Output limit

**Hard limit: 100 lines, compressed format only.**
Drop articles, filler, full sentences. Fragments + bullets only.
No conversation recap. No verbose explanations. Technical state only.

---

## Step 1: Gather state (bash)

```bash
git branch --show-current
git log --oneline -3
git diff --stat HEAD
```

## Step 2: Write handoff file

**Path:** `memory/features/{slug}/session-{YYYYMMDD-HHMMSS}.md`

**Template (stay under 100 lines):**

```markdown
# Handoff: {slug} {YYYYMMDD-HHMM}

Branch: {branch} | Phase: {phase} | Story: {STORY-KEY or —}

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

## Step 3: Cleanup old sessions

Keep last 3 session files in `memory/features/{slug}/`. Delete older ones inline.

## Step 4: Confirm + clear

Print:

```
Handoff saved: memory/features/{slug}/session-{ts}.md
Clearing context...
```

Then run `/clear`.
