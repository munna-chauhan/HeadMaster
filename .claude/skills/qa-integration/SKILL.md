---
name: qa-integration
description: "Inline phase D of /execute. Writes + runs integration tests per AC. Owns test fixes. Reports code bugs. Never touches production code."
argument-hint: <story-key> <slug>
---

# QA Integration

Load `.claude/agents/qa-engineer.md` constraints.

Verify every AC via integration tests. Own test wrong → fix it. Code bug → report it. **Never touch production code.**

---

## Context (from execute — already cached)

```
story_key, slug, branch, repo_path, build_cmd,
acs[],            ← acceptance criteria
tdd_test_section  ← TDD S7 only (search by heading, do not read full TDD)
```

Read `memory/features/{slug}/agents/qa-engineer.md` if exists.

---

## Steps

**1. Setup**

```bash
cd {repo_path}
git checkout story/{STORY-KEY} && git pull
{build_cmd}
```

Build fails → REJECTED-BUG immediately.

**2. Per AC**

- Map to test scenario from TDD S7 + existing test patterns
- Write integration test (Given/When/Then matching AC)
- Run → evaluate:
    - Own test wrong → fix, re-run (max 2 self-corrections per AC)
    - Code bug → record, do not fix

**3. Regression** — affected module only:

```bash
# Maven: mvn test -pl {module}
# Gradle: ./gradlew :{module}:test
# npm:    npm test -- --testPathPattern={module}
# pytest: python -m pytest {module}/
```

**4. Write report**

**Path:** `docs/features/{slug}/execution/reviews/qa-report-{STORY-KEY}.md`

```markdown
# QA Report: {STORY-KEY}
Verdict: {APPROVED|REJECTED-BUG} | Build: {PASS|FAIL} | {ISO-date}

## AC Results
| AC# | Status | Evidence |
|-----|--------|----------|
| 1   | PASS   | {test + output} |
| 2   | FAIL   | {expected vs actual} |

## Bugs
- AC{N}: {expected} vs {actual} | Repro: `{command}`

## Regression
| Module | Run | Pass | Fail |
```

**5. Update memory** `memory/features/{slug}/agents/qa-engineer.md` (max 200 words)

---

## Verdict

- APPROVED: all ACs PASS + regression green
- REJECTED-BUG: any AC fails due to code bug → back to implement

## Constraints

- Story branch only
- Every AC must have result — no untested ACs
- Max 2 self-corrections before escalating as code bug
