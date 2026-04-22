<div align="center">

<img src="./HeadMaster_Logo.png" alt="HeadMaster Logo" width="175"/>

# HeadMaster ADLC

### Autonomous Development Lifecycle using Claude Code

**Describe a feature → get a production-ready PR.**

HeadMaster is an autonomous SDLC orchestrator that converts a feature description into a production-ready pull request
using multi-agent execution, deterministic gates, and context-bounded reasoning.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Required-D97706?style=flat&logo=anthropic&logoColor=white)](https://docs.anthropic.com/en/docs/claude-code)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat)](LICENSE)

[Quick Start](#-quick-start) • [What Makes It Different](#-what-makes-headmaster-different) • [Example](#-example-45-minutes-end-to-end)

</div>

---

## 💡 What Is HeadMaster?

Traditional AI copilots assist developers.
**HeadMaster executes the entire development lifecycle**—you only make decisions at key checkpoints.

**You provide:**

* A feature description

**HeadMaster handles:**

* PRD → Design → Implementation → Testing → Review → PR

**Your time:** ~5–15 minutes
**Total execution:** ~45–120 minutes

---

## 🧭 How to Read This README

* New user → Start with **Quick Start**
* Evaluating system → Read **3-Gate Workflow** + **What Makes It Different**
* Debugging → Go to **Troubleshooting**

| Feature                          | What It Does                                                     | Impact                              |
|----------------------------------|------------------------------------------------------------------|-------------------------------------|
| **🤖 Full SDLC Automation**      | PRD → Design → Implementation → Testing → PR                     | 90% time saved vs manual            |
| **🧠 Complexity Auto-Detection** | Lite (6-section PRD) → Full (14-section) based on scope          | No over-engineering small features  |
| **👁️ Isolated Agent Reviews**   | Code reviewer sees only git diff (no implementation context)     | Catches "I know what I meant" bugs  |
| **🔄 Intelligent Retry Logic**   | Blocks retry approaches with 70%+ word overlap to prior failures | No infinite loops                   |
| **🎯 Convergence Detection**     | Detects oscillating review loops → auto-escalates after 3x       | No "fix A breaks B" cycles          |
| **💰 Cost Optimization**         | Opus for design, Sonnet for code, Haiku for checklists           | 60-80% savings vs "Opus everywhere" |
| **📊 Session Age Management**    | Auto-checkpoint at 25 turns, auto-handoff at 35                  | Handles multi-hour executions       |
| **🔒 Production-Safe**           | Git guard blocks force-push/hard-reset, secret scanner           | No accidental data loss             |

## 🔥 What Makes HeadMaster Different?

### Claude in a Loop

| Capability             | Naive Loop                      | HeadMaster                              |
|------------------------|---------------------------------|-----------------------------------------|
| **Context Management** | 💥 Blows up after 3-4 stories   | ✅ Distillation chain + lazy loading     |
| **Review Isolation**   | ❌ Reviewer knows implementation | ✅ Fresh context, diff-only              |
| **Infinite Loops**     | 💥 Fix A → breaks B → repeat    | ✅ Convergence detection + escalation    |
| **Session Crashes**    | 💥 Lost work                    | ✅ Auto-checkpoints + recovery           |
| **Token Usage**        | 💸 500K+ for 5-story feature    | ✅ 100-150K (lazy loading + compression) |
| **Cost**               | 💸 $20-40 per feature           | ✅ $5-10 per feature (model routing)     |

### Key Innovations

#### 1. **Isolated Agent Reviews** (Genuine Fresh Eyes)

```
Developer agent:
  Knows: TDD section for this story
  Doesn't know: PRD, upstream design decisions, other stories

Code reviewer agent:
  Knows: Git diff only (this commit)
  Doesn't know: TDD, implementation context, why developer chose this approach
  
QA agent:
  Knows: Acceptance criteria only
  Doesn't know: Implementation, review findings

System reviewer:
  Knows: TDD design + final git log
  Doesn't know: Per-story struggles, retry history
```

**Why this matters:** Catches bugs the implementer missed due to "I know what I meant" blindness.


---

## ⚡ Quick Start

```bash
git clone <repository>
cd HeadMaster
pip install -r requirements.txt

cp .claude/settings.local.json.example .claude/settings.local.json
```

Edit `config.yml`:

```yaml
interactive: false   # Autonomous mode (only asks when confused)
jira_push: true      # Auto-push stories to Jira after Gate 1
project_key: "PROJ"  # Your Jira project key
```

Set Jira credentials (one-time):

```powershell
# Windows PowerShell
[System.Environment]::SetEnvironmentVariable("ATLASSIAN_DOMAIN", "company.atlassian.net", "User")
[System.Environment]::SetEnvironmentVariable("JIRA_USER_EMAIL", "you@company.com", "User")
[System.Environment]::SetEnvironmentVariable("JIRA_API_TOKEN", "your-token", "User")

# Restart terminal for changes to take effect
```

Get token: https://id.atlassian.com/manage-profile/security/api-tokens

### 3. Start Your First Feature (1 command)

```bash
claude --name "my-feature"
/navigate "Add rate limiting to public API - 100 req/min per client"
```

That’s it. HeadMaster executes the full pipeline.

---

## 🎯 The 3-Gate Workflow

HeadMaster only stops at three points:

### Gate 1 — Stories (2 min)

You review and approve generated stories.

### Gate 2 — Escalation (rare)

Triggered only if a story fails 3 times.

### Gate 3 — PR (3–5 min)

You review and merge.

Everything else is autonomous.

---

## 💰 Cost Optimization

HeadMaster uses **model routing** to minimize cost without sacrificing quality:

```
Typical 5-story feature:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Naive (Opus everywhere):        $35-50
HeadMaster (model routing):     $6-10    (85% savings)

Breakdown:
  Opus 4.7 (30K tokens):        $2   (architecture only)
  Sonnet 4.6 (120K tokens):     $6   (code, PRD, reviews)
  Haiku 4.5 (50K tokens):       $0.50 (checklists, search)
  Scripts (0 tokens):           $0   (gate checks, compression)
```

Additional optimizations:

- **Complexity tiers:** Lite features use 6-section PRD (not 14)
- **Lazy loading:** Skills load stages on-demand (~300 tokens saved/invocation)
- **Read compression:** Memory files compressed 30-60% before Claude sees them
- **Stop hooks:** Python scripts replace Haiku calls for deterministic checks
- **Context discipline:** Each phase loads only required artifacts

---

## 🛡️ Reliability & Safety

### Git Protection

Blocks destructive commands:

* force push
* hard reset
* clean wipe

---

### Crash Recovery

```bash
# Session died mid-execution?
/execute my-feature  # Resume command

# Pre-flight checks:
✅ Branch integrity (dirty working tree → stash/reset)
✅ Build status (broken → soft reset HEAD~1)
✅ Task list sync (resume from last completed story)
```

### Intelligent Retry Logic

```
Attempt 1: SQL concatenation → SQL injection detected
Attempt 2: PreparedStatement → ✅ Structurally different (allowed)
Attempt 3: String interpolation → ❌ 85% word overlap with attempt 1 (BLOCKED)
           → Escalate to Gate 2
```

### Convergence Detection

```
Iteration 1: Fixed blocker A
Iteration 2: Fixed blocker B
Iteration 3: Blocker A reappeared (oscillation detected)
            → Auto-escalate to Gate 2
```

### Session Age Management

```
Turn 5 → Yellow warning (keep working)
Turn 10 → Orange warning + auto-checkpoint saved
Turn 15 → Red alert + auto-handoff required

Turn count persists across Claude sessions.
Manual reset: python scripts/reset_session_budget.py
```

---

## 📊 Complexity Tiers (Auto-Detected)

Not every feature needs a 14-section PRD. HeadMaster auto-classifies:

| Tier            | Stories | Repos | PRD Sections | Design                            | Example                                    |
|-----------------|---------|-------|--------------|-----------------------------------|--------------------------------------------|
| **🟢 Lite**     | 1-2     | 1     | 6            | IMPLEMENTATION_BRIEF (5 sections) | "Add validation to form field"             |
| **🟡 Standard** | 3-5     | 1-2   | 10           | TDD.md (8 sections)               | "Add export feature with 3 formats"        |
| **🔴 Full**     | 6+      | 2+    | 14           | TDD_MASTER + per-repo TDDs        | "Migrate Elasticsearch 5→9 across 5 repos" |

**Override:** `/navigate my-feature --tier lite` (if AI misclassifies)

**Why tiers matter:**

- Lite features ship in 30-60 minutes (not 3 hours)
- No over-engineering small changes
- Documentation matches complexity

---

## ⚠️ When HeadMaster Fails

Common patterns:

### 1. Weak PRD → Poor Output

Fix: Spend more time at Gate 1

---

### 2. Story Fails Repeatedly

Fix: Review escalation logs and guide manually

---

### 3. Wrong Complexity Tier

Fix:

```bash
/navigate feature --tier lite
```

---

## 📊 Performance Monitoring

Passive monitoring via PostToolUse hooks (zero user friction):

**What's tracked:**

- Tool calls per feature (`skill_metrics.json`)
- Phase durations, iterations (`phase_performance.json`)
- Regression detection (50% slower than baseline → alert)

**Commands:**

```bash
/skill-monitor dashboard           # Global performance summary
/skill-monitor analyze <slug>      # Per-feature deep dive
/skill-monitor list-alerts         # Show regressions
/skill-monitor update-baseline <phase>  # Refresh baseline
```

**Configuration:** `config.yml` → `skill_monitoring` section (enabled: true, alert_threshold: 1.5)  
**Data location:** `memory/features/{slug}/` + `memory/baselines/`  
**Disable:** `bash scripts/disable_monitoring.sh`

---

## 🐛 Troubleshooting

| Problem                  | Solution                                                         |
|--------------------------|------------------------------------------------------------------|
| **Feature not resuming** | `/navigate {slug}` — detects phase from artifacts                |
| **Undo changes**         | `Esc + Esc` → checkpoint picker                                  |
| **Review loop stuck**    | Check `memory/features/{slug}/loop_state.json` → iteration count |
| **Jira push failing**    | Verify env vars: `echo $env:JIRA_USER_EMAIL`                     |
| **Story failed 3x**      | Check `execution/reviews/escalation-{STORY}.md`                  |
| **Session age ⛔**        | Run `/handoff` at 🟠, or increase `turn_warn_red` in config      |
| **Hook errors**          | Status shows ⚠️, check `~/memory/hook-errors.log`                |

---

## 🏗️ Architecture Highlights

### Single Source of Truth (Distillation Chain)

```
Raw input → FEATURE_DRAFT.md → PRD.md (approved)
  ↓
PRD.md → SYSTEM_DESIGN_NOTES.md → TDD.md (approved)
  ↓
TDD.md → JIRA_BREAKDOWN.md (approved)
  ↓
JIRA_BREAKDOWN.md → Per-story implementation

Each phase distills upstream work.
Once distilled, upstream artifacts are never reloaded.
Result: Context stays bounded even on 10-story features.
```

### Isolated Agents (Fresh Eyes)

```
Developer:       Knows TDD section only
Code Reviewer:   Knows git diff only (no TDD, no context)
QA Engineer:     Knows ACs only (no code, no review findings)
System Reviewer: Knows TDD + git log (finds design divergences)

Why? Prevents "I know what I meant" blindness.
```

## ⚠️ Limitations

* Depends on input quality (Gate 1 critical)
* No built-in self-test suite yet
* Optimized for Claude Code
* Single-user workflow (multi-user in progress)

---

## 🚀 Get Started

```bash
claude --name "my-feature"
/navigate "describe your feature"
```

HeadMaster takes it from there.

---

**License:** Apache 2.0
**Requirements:** Python 3.10+, Claude Code
**Optional:** Jira integration
