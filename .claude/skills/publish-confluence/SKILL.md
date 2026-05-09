---
name: publish-confluence
description: Publish a pipeline artifact (PRD, TDD) to Confluence. Handles markdown conversion, frontmatter stripping, diagrams/Mermaid code macros, and table formatting.
argument-hint: <feature-slug> <artifact> [--page-id <id> | --folder-id <id> | --parent-id <id>]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# You are publishing a pipeline artifact to Confluence

## Execution Steps

### Step 1: Validate

- Resolve artifact path from the by project and slug `docs/features/{project}/{slug}/*` or artifact path.
- HALT if file does not exist
- Resolve target from argument:
    - `--page-id <id>` → replace existing page
    - `--folder-id <id>` → create new page inside folder
    - `--parent-id <id>` → create new page as child of parent
- Extract numeric ID from argument — accept either bare ID (`123456789`) or full Atlassian URL (extract the numeric
  segment)

### Step 2: Pre-process

Run:

```bash
python .claude/skills/publish-confluence/scripts/confluence_publish.py preprocess <file-path>
```

This produces a temporary processed file. The script handles:

- Strip pipeline frontmatter (lines from start up to and including the first `---` separator)
- Convert Markdown tables to Confluence storage `<table>` format
- Wrap each Mermaid block with a label and Confluence code macro
- Convert headers, bold, italic, inline code, ordered/unordered lists, horizontal rules
- Remove any remaining pipeline-internal references (FEATURE_DRAFT.md, DISCOVERY_NOTES.md mentions)

### Step 3: Confirm

Always show confirmation before publishing — never publish silently:

```
📄 Artifact : {artifact} — {title from file}
📍 Target   : {replace page <id> | new page in folder <id> | new child of <id>}
🔑 Space    : {space_key from config}

Proceed? [y/N]:
```

If user enters anything other than `y` or `Y`: abort, log `Publish cancelled`.

### Step 4: Publish

**Replace existing page (`--page-id`):**

```bash
python .claude/skills/publish-confluence/scripts/confluence_publish.py update <page-id> <processed-file> "<title>"
```

**New page in folder or under parent (`--folder-id` or `--parent-id`):**

```bash
python .claude/skills/publish-confluence/scripts/confluence_publish.py create "<title>" <processed-file> <parent-or-folder-id>
```

### Step 5: Output

```
✅ Published successfully
📄 {artifact}: {title}
🔗 {full Confluence URL}
```

On failure: print the error from the script and HALT. Do not retry automatically.

---

## Prerequisites

- `ATLASSIAN_DOMAIN`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN` environment variables set
- `integrations.confluence.enabled: true` in resolved config
- `projects.{project}.confluence: true` to check the permission
- `python .claude/skills/publish-confluence/scripts/confluence_publish.py` exists (pre-processing script)
