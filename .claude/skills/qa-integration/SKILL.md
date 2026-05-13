---
name: qa-integration
description: "Integration QA skill. Writes + runs integration tests against story or feature ACs. Used as subagent in Phase C of /execute. Owns test fixes. Reports code bugs. Never touches production code."
argument-hint: <story-key> <slug>
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# QA Integration

Execute per `.claude/agents/qa-engineer.md` — agent owns classification, test methodology, verdicts, and constraints.

---

## Context (from execute — already cached)

```
story_key, slug, branch, repo_path, build_cmd,
acs[],            ← acceptance criteria
tdd_test_section  ← TDD S7 only (search by heading, do not read full TDD)
```

Read `memory/agents/qa-engineer/MEMORY.md` if exists.

---

## Steps

**0. Detect Test Infrastructure (mandatory first step)**

```bash
python .claude/skills/qa-integration/scripts/test_infra_detector.py --repo {repo_path} --format json
```

**TDD Strategy Validation (after detector runs):**

Read TDD S7 from `tdd_test_section`. Compare required infra against detector output:

| Infra class | Missing action |
|-------------|---------------|
| CRITICAL (Testcontainers, WireMock, MockMvc, LocalStack, embedded Kafka) | Escalate — QA cannot proceed |
| NON-CRITICAL (H2, in-memory stores, embedded Redis) | Log WARNING, continue with degraded confidence |

**1. Setup**

```bash
cd {repo_path}
git checkout story/{STORY-KEY} && git pull
{build_cmd}
```

Build fails → REJECTED-BUG immediately.

**2–3. Classify ACs + verify**

Agent owns per `.claude/agents/qa-engineer.md`.

**4. Regression** — affected module only:

```bash
# Maven: mvn test -pl {module}
# Gradle: ./gradlew :{module}:test
# npm:    npm test -- --testPathPattern={module}
# pytest: python -m pytest {module}/
```

**5. Write report**

Path: `docs/features/{project}/{slug}/execution/reviews/qa-report-{STORY-KEY}.md`

Format per `.claude/agents/references/qa-report.example.md`.

**6. Update memory** `memory/agents/qa-engineer/MEMORY.md` (max 200 words)
