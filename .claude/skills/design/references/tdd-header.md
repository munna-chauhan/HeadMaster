# TDD Header Template

All TDD documents use this format. H1 heading MUST be line 1, metadata table at line 3.

```markdown
# {Feature Name} — Technical Design Document

| Field              | Value                                     |
|--------------------|-------------------------------------------|
| Technical Owner*   | {from PRD}                                |
| AI Co-Author       | Agent - TDD Author                        |
| Date*              | {ISO-date}                                |
| Version            | {version number + brief change desc}      |
| Complexity Tier    | {Extra Small | Small | Medium | Large}    |
| Next Steps         | {see below}                               |
```

**Additional rows:**

| Document | Extra Row |
|----------|-----------|
| TDD_MASTER.md | `Review Status: {PASS \| CONDITIONAL \| BLOCKED}` |
| TDD_{REPO}.md | `Parent TDD: [TDD_MASTER.md](TDD_MASTER.md)` |

**Next Steps values:**

| State | Value |
|-------|-------|
| Draft | "TDD review" or "Address review findings" |
| Approved | "/breakdown {slug}" |
| xs (IMPLEMENTATION_BRIEF) | "/breakdown {slug}" |

**Validation (before writing):**
1. H1 heading at line 1
2. Metadata table starts at line 3
3. 6 base rows (+ 1 for MASTER/REPO variants)
4. No: Feature Folder, PRD Version, Design Iteration, Document Type, Status fields
