---
name: compress
description: "Compress natural language .md files to concise style — saves input tokens every session. Preserves code blocks, URLs, headings, structure. Overwrites original, saves backup as .original.md. Safe scope: memory files, CLAUDE.md, session notes, working files only."
argument-hint: <filepath>
---

# Compress

Compress file to concise style. Save tokens every session. Never touch code, config, or formal artifacts.

---

## Trigger

`/compress <filepath>` — compresses a natural language file to concise format.

---

## Compression Style

Compressed output must follow compression rules:

- Drop articles (a, an, the)
- Drop filler (just, really, basically, in order to, please note)
- Drop hedging (might, could potentially, it seems)
- Fragments OK — full sentences not required
- `→` for causality instead of "because", "therefore", "which means"
- Tables over prose for comparisons
- Code/paths/commands exact — never touch these
- Technical terms, library names, API names — never touch

**What is preserved exactly:**

- Code blocks (fenced + indented)
- Inline backticks
- URLs and links
- File paths
- Commands
- Headings (exact text)
- Table structure (cell text compressed)
- Dates, version numbers, numeric values

---

## Safe Scope

**Compress these:**

- `memory/` files — agent memory, session notes, decisions
- `CLAUDE.md` — project instructions
- Working files — FEATURE_DRAFT.md, DISCOVERY_NOTES.md
- Personal notes, todos, preferences

**Never compress these — formal artifacts:**

- `PRD.md`, `TDD*.md`, `SYSTEM_DESIGN_NOTES.md` — formal specs
- `JIRA_BREAKDOWN.md` — execution tracker
- `*_REVIEW.md` — review artifacts
- Code files (`.py`, `.js`, `.ts`, `.java`, etc.)
- Config files (`.json`, `.yaml`, `.toml`, `.yml`)
- Files with sensitive names (credentials, secrets, keys, `.env`)
- Backup files (`*.original.md`)

If file is in the "never compress" list → HALT, tell user why.

---

## Process

```
1. Scope     → check against safe scope list. Formal artifacts → HALT.
2. Backup    → save original as <filename>.original.md
               If backup already exists → HALT (prevent data loss)
3. Compress  → python3 scripts/compress.py (inline regex compression)
               No API calls — preserves code/URLs/paths, drops filler/articles
4. Validate  → Manual verification:
               - Heading count + order preserved
               - Code blocks exact
               - URLs preserved
               - File paths intact
5. Write     → compressed output overwrites original file path
```

**Note:** This uses regex-based inline compression (no LLM calls). For files needing deeper compression, manually review and edit.

---

## Usage

```bash
# Compress agent memory
/compress memory/features/my-feature/decisions.md

# Compress project instructions
/compress .claude/CLAUDE.md

# Compress working file
/compress docs/features/my-feature/planning/FEATURE_DRAFT.md
```

---

## Benchmarks (from compression benchmarks)

| File               | Original | Compressed | Saved   |
|--------------------|----------|------------|---------|
| preferences.md     | 706      | 285        | 60%     |
| project-notes.md   | 1145     | 535        | 53%     |
| project.md         | 1122     | 636        | 43%     |
| todo-list.md       | 627      | 388        | 38%     |
| mixed-with-code.md | 888      | 560        | 37%     |
| **Average**        | **898**  | **481**    | **46%** |

CLAUDE.md loads every session. 1000-token file × 100 sessions = 100k tokens overhead. Compress once → save forever.
