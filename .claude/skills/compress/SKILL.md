---
name: compress
description: "Compress natural language .md files to concise style — saves input tokens every session. Preserves code blocks, URLs, headings, structure. Overwrites original, saves backup as .original.md. Safe scope: memory files, CLAUDE.md, session notes, working files only."
argument-hint: <filepath>
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Compress

Compress file to concise style. Save tokens every session. Never touch code, config, or formal artifacts.

---

## Safe Scope

Safe scope enforced by `scripts/compress.py` (`NEVER_COMPRESS` and `NEVER_COMPRESS_PATTERNS` constants). The script is the source of truth.

**Compress:** `memory/` files, `CLAUDE.md`, working files (FEATURE_DRAFT.md, DISCOVERY_NOTES.md), personal notes.

**Never compress:** formal specs, review artifacts, code files, config files, backups.

---

## Process

```
1. Scope     → check against safe scope. Formal artifacts → HALT.
2. Backup    → save original as <filename>.original.md
               If backup already exists → HALT (prevent data loss)
3. Compress  → mode depends on target (see below)
4. Validate  → heading count + order preserved, code blocks exact, URLs intact
5. Write     → compressed output overwrites original file path
```

### Mode: Agent Memory (`memory/agents/{agent}/MEMORY.md`)

Spawn `retrospective-analyst`:

```
Curate this agent memory file. Rules:
- Merge entries that express the same learning
- Drop entries too feature-specific to generalize
- Drop entries older than 90 days if superseded by newer entry on same topic
- Rewrite vague entries into sharp, actionable rules
- Preserve section structure (## Patterns / ## Pitfalls / ## Project-Specific)
- Output full rewritten MEMORY.md — same format, better content
```

Show diff to user before writing. Apply on confirmation.

### Mode: All Other Files

Run `scripts/compress.py` — regex-based, no LLM calls. Drops filler/articles/hedging, preserves code/URLs/paths exactly. Compression rules defined in the script.
