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
1. Detect    → detect.py classifies file. Only natural_language proceeds.
2. Scope     → check against safe scope list. Formal artifacts → HALT.
3. Backup    → save original as <filename>.original.md
               If backup already exists → HALT (prevent data loss)
4. Compress  → compress.py sends content to Claude with compression rules above.
               Model: HEAD_MASTER_COMPRESS_MODEL env var (default: claude-haiku-4-5)
               Use haiku — compression is mechanical, not creative.
5. Validate  → validate.py checks:
               - Heading count + order preserved
               - Code blocks exact
               - URL set equal
               - File paths preserved
               - Bullet count drift < 20%
6. Retry     → If validation fails: targeted fix prompt only — patch broken parts,
               do NOT recompress full file. Up to 2 retry attempts.
               If all retries fail → restore original, remove backup.
7. Write     → compressed output overwrites original file path
```

---

## Retry Strategy (token-efficient)

On validation failure, send only the broken parts to Claude with targeted fix prompt — not the full file. This costs a
fraction of a full recompress.

```
Fix prompt: "Fix only these validation errors in the compressed output:
{specific errors}
Do not change anything else."
```

---

## Requirements

- Python 3.10+
- `ANTHROPIC_API_KEY` env var (uses `anthropic` SDK) or `claude` CLI on PATH
- Model: `HEAD_MASTER_COMPRESS_MODEL` env var (default: `claude-haiku-4-5`)

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
