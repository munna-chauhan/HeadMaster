---
name: complexity
description: Analyze branch diff size and risk indicators. LOC-based scope assessment (not pipeline tier classification).
---

# /complexity

Compare current branch with main to understand feature scope by diff size.

**Note:** This measures LOC changed (diff size). It is NOT the pipeline complexity tier (xs/s/m/l) which is based on story count and SP. Use this for scope awareness, not tier classification.

## Steps

### 1. Gather metrics

```
git diff main --stat
git diff main --numstat
git rev-list --count main..HEAD
```

### 2. Run analysis

```
sh scripts/analyze_complexity.py -q
```

### 3. Output

Report: files changed, insertions/deletions, net LOC, commits, diff size tier, top changed files, risk indicators, recommendation.

## Diff Size Tiers (LOC-based)

| Tier | LOC Changed | Expectation |
|---|---|---|
| 🟢 SMALL | <500 | Quick review |
| 🟡 MEDIUM | 500–2K | 1-2 review rounds |
| 🟠 LARGE | 2K–5K | Multi-day, may need breakup |
| 🔴 X-LARGE | 5K+ | Definitely needs breakdown |
