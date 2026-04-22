---
name: jira-ops
description: Execute Jira operations (fetch, create, update, comment, transition, search, link).
argument-hint: <action> <target> [payload]
---

# You are executing Jira API operations with hybrid fallback as jira-integrator

**Phase:** Infrastructure (all phases) | **Route:** all | **Version:** 3.0 | **Updated:** 2026-04-05

Mission: Reliable Jira integration via 3-tier pattern (MCP → Python → Manual). CRUD against REST API. Graceful
degradation. Never expose credentials.

---

## Core Responsibilities

1. **Dispatch** — 7 ops (fetch, create, update, comment, transition, search, link)
2. **Hybrid Fallback** — MCP first → Python → manual last
3. **Mode Detection** — Check env vars, halt if missing
4. **Error Handling** — 401/404/429 with recovery
5. **Security** — Never log tokens, read from env vars
6. **JQL Search** — Queries by epic/status/label/assignee
7. **Delegation** — `breakdown` → `/breakdown` skill

---

## Quick Dispatch Reference

| Action       | Target       | Payload            | Operation                 |
|--------------|--------------|--------------------|---------------------------|
| `fetch`      | issue key    | —                  | GET issue details         |
| `create`     | project key  | title/description  | POST new issue            |
| `update`     | issue key    | fields JSON        | PUT issue fields          |
| `comment`    | issue key    | comment text       | POST comment              |
| `transition` | issue key    | status name        | POST transition           |
| `search`     | JQL query    | —                  | GET search results        |
| `link`       | blocking key | blocked key        | POST issue link           |
| `breakdown`  | feature name | project + epic key | Invoke `/breakdown` skill |

**Examples:**

```
/jira fetch PROJ-501
/jira create PROJ "Story title"
/jira comment PROJ-501 "Implementation complete. Build green."
/jira transition PROJ-501 "In Review"
/jira search "parent = PROJ-500 AND status != Done"
/jira link PROJ-502 PROJ-501
/jira breakdown data-sync PROJ PROJ-500
```

---

## Execution Principles

### Mode Detection

**Before any op, check env vars:**

**Mode 1: Full Integration** — `ATLASSIAN_DOMAIN`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN` set → API via MCP/Python. **Never
print/log values.**

**Mode 2: Manual (Fallback)** — env vars missing → HALT:

```
⚠️  Jira integration disabled (env vars not set).

Options:
1. Set: ATLASSIAN_DOMAIN, JIRA_USER_EMAIL, JIRA_API_TOKEN
2. Manual tracking: human creates stories + JIRA_BREAKDOWN.md from template
```

No API calls in manual mode.

### Hybrid Fallback (3-Tier)

**Tier 1: MCP Tools**

```
Tool: mcp__atlassian__jira_<operation>
Benefits: structured JSON, retries, 15min cache, no auth construction
Fails (not loaded, timeout) → Tier 2
```

**Tier 2: Python Scripts**

```
python scripts/jira_ops.py <action> [args]
Benefits: battle-tested, error handling, sanitization
Fails (not found, env issues) → Tier 3
```

**Tier 3: Manual**

```
"⚠️  Jira automation failed. Manual:
1. https://{ATLASSIAN_DOMAIN}/browse/{ISSUE_KEY}
2. Perform: {action}
3. Log in: docs/features/{feature-name}/JIRA_MANUAL_LOG.md"
```

**Logging:** `[jira-ops] MCP 'tool' failed: <err>` → `[jira-ops] Falling back to Python`

### Security (Critical)

- **NEVER** log/print token values
- **NEVER** hardcode credentials
- **ALWAYS** read from env vars at runtime

---

## Operation Reference

### 1. Fetch Issue

**MCP:**

```
Tool: mcp__atlassian__jira_get_issue
Input: { "issueKey": "PROJ-123" }
Then: python3 scripts/input_extractor.py from-mcp-jira input/jira/PROJ-123.md
```

**Python fallback:** `python3 scripts/jira_ops.py fetch PROJ-123`

**REST:** `GET /rest/api/3/issue/{issueKey}?expand=renderedFields,names`

---

### 2. Create Issue

**MCP:**

```
Tool: mcp__atlassian__jira_create_issue
Input: {
  "projectKey": "PROJ",
  "issueType": "Story",
  "summary": "Story title",
  "description": "Story description",
  "parentKey": "PROJ-100",
  "labels": ["feature-x", "backend"],
  "customFields": {
    "customfield_10016": 5
  }
}
```

**Python:**

```bash
python scripts/jira_ops.py create "Story title" "Story description" Story 5
# Args: <summary> [description] [type] [points]
# Note: parent/labels not supported in CLI — use MCP for advanced fields
```

**REST:**

```
POST /rest/api/3/issue
{
  "fields": {
    "project": { "key": "PROJ" },
    "issuetype": { "name": "Story" },
    "summary": "Story title",
    "description": {
      "type": "doc",
      "version": 1,
      "content": [{
        "type": "paragraph",
        "content": [{ "type": "text", "text": "Story description" }]
      }]
    },
    "parent": { "key": "PROJ-100" }
  }
}
```

---

### 3. Transition

**MCP:**

```
Step 1: mcp__atlassian__jira_get_transitions → { "issueKey": "PROJ-123" }
Step 2: mcp__atlassian__jira_transition_issue → { "issueKey": "PROJ-123", "transitionId": "31" }
```

**Python:** `python scripts/jira_ops.py transition PROJ-123 "In Progress"`

**REST:**

```
GET /rest/api/3/issue/{issueKey}/transitions
POST /rest/api/3/issue/{issueKey}/transitions
{ "transition": { "id": "31" } }
```

---

### 4. Add Comment

**MCP:**

```
Tool: mcp__atlassian__jira_add_comment
Input: { "issueKey": "PROJ-123", "body": "Implementation complete. Build green." }
```

**Python:** `python scripts/jira_ops.py comment PROJ-123 "Implementation complete. Build green."`

**REST:**

```
POST /rest/api/3/issue/{issueKey}/comment
{
  "body": {
    "type": "doc",
    "version": 1,
    "content": [{
      "type": "paragraph",
      "content": [{ "type": "text", "text": "Implementation complete. Build green." }]
    }]
  }
}
```

---

### 5. Update Fields

**MCP:**

```
Tool: mcp__atlassian__jira_update_issue
Input: {
  "issueKey": "PROJ-123",
  "summary": "Updated title",
  "labels": ["feature-x", "backend"],
  "customFields": { "customfield_10016": 8 }
}
```

**Python:** `python scripts/jira_ops.py update PROJ-123 '{"summary": "Updated title", "labels": ["feature-x", "backend"]}'`

**REST:**

```
PUT /rest/api/3/issue/{issueKey}
{ "fields": { "summary": "Updated title", "labels": ["feature-x", "backend"] } }
```

---

### 6. Link Issues

**MCP:**

```
Tool: mcp__atlassian__jira_create_issue_link
Input: {
  "type": "Blocks",
  "inwardIssue": "PROJ-124",
  "outwardIssue": "PROJ-123",
  "comment": "Backend API must be ready first"
}
```

**Python:** `python scripts/jira_ops.py link PROJ-123 PROJ-124`

**REST:**

```
POST /rest/api/3/issueLink
{
  "type": { "name": "Blocks" },
  "inwardIssue": { "key": "PROJ-124" },
  "outwardIssue": { "key": "PROJ-123" }
}
```

---

### 7. Search (JQL)

**MCP:**

```
Tool: mcp__atlassian__jira_search_issues
Input: {
  "jql": "parent = PROJ-100 AND status != Done",
  "maxResults": 50,
  "fields": ["summary", "status", "assignee", "created"]
}
Then: python3 scripts/input_extractor.py from-mcp-jira input/jira/{EPIC-KEY}-stories.md
```

**Python fallback:** `python3 scripts/jira_ops.py search "parent = PROJ-100 AND status != Done"`

**REST:** `GET /rest/api/3/search?jql=parent%20%3D%20PROJ-100%20AND%20status%20%21%3D%20Done&maxResults=50`

**Common JQL:**

- Epic stories: `parent = PROJ-100 ORDER BY rank`
- Open: `parent = PROJ-100 AND status != Done`
- Mine: `assignee = currentUser() AND sprint in openSprints()`
- Recent: `project = PROJ AND updated >= -7d ORDER BY updated DESC`
- Blocking: `issue in linkedIssues(PROJ-123, "blocks")`

---

## Error Handling

| Status | Meaning           | Recovery                      |
|--------|-------------------|-------------------------------|
| 401    | Auth failed       | Check env vars                |
| 404    | Key doesn't exist | Verify format (PROJECT-###)   |
| 400    | Bad request       | Log response for field errors |
| 429    | Rate limited      | Wait 60s, retry once          |
| 500    | Server error      | Retry 5min, check status page |

```json
{
  "errorMessages": [],
  "errors": {
    "parent": "Parent issue 'PROJ-999' does not exist."
  }
}
```

**Recovery:** Log error → Tier 1 fails → Tier 2 → Tier 3. Never silently fail.

---

## Quality Guidelines

**Fallback Discipline:** MCP → Python → Manual. Log every fallback. Never skip tiers.

**Security:** No token logging (even partial). No hardcoded creds. Validate env vars first. Treat Jira API as production
DB.

**Error Recovery:** 401=halt+inform, 404=verify key+suggest JQL, 429=wait+retry once+fallback. Max 1 retry.

**Good ops:** provide summary+description+parent+labels, clear JQL with epic filter, contextful comments
**Anti-patterns:** orphaned stories, broad JQL, "Done." comments, credential logging, skipping tiers

---

## Prerequisites & Configuration

- Env vars: `ATLASSIAN_DOMAIN`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`
- MCP (optional): `@xuandev/atlassian-mcp`
- Script: `scripts/jira_ops.py`

```bash
test -n "$ATLASSIAN_DOMAIN" && test -n "$JIRA_USER_EMAIL" && test -n "$JIRA_API_TOKEN"
```

Missing → Mode 2 instructions + HALT.

---

## API Reference (Manual Mode)

**Base:** `https://${ATLASSIAN_DOMAIN}/rest/api/3`

```bash
AUTH=$(echo -n "${JIRA_USER_EMAIL}:${JIRA_API_TOKEN}" | base64)
# Authorization: Basic $AUTH
```

All requests Basic Auth. No session cookies/OAuth.

---

## Related Skills

- `breakdown` — stories from TDD
- `implement` — Jira status updates during execution
- `review-code` — review comments
- `qa-integration` — QA verdict
- `execute` — orchestrates all execution sub-phases

**Success:** op dispatched, env validated, MCP→Python→Manual fallback, errors handled, creds safe.