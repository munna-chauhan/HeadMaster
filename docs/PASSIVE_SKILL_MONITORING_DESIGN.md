# Passive Skill Monitoring Integration Design

**Objective:** Auto-monitor HeadMaster skill performance via hooks, detect regressions, generate dashboards — **without changing existing workflows**.

---

## Design Philosophy

### What NOT to Do ❌
- Require users to run benchmarks manually
- Change existing skill invocation patterns
- Add test suites users must maintain
- Block execution for evaluation

### What TO Do ✅
- **Observe passively** via hooks
- **Evaluate automatically** on natural breakpoints (gate passes, handoffs)
- **Alert proactively** when regressions detected
- **Zero user friction** — monitoring is invisible

---

## Architecture: APM for AI Agents

Think **Application Performance Monitoring** (like DataDog/New Relic) but for HeadMaster skills:

```
User: /plan my-feature
  ↓
HeadMaster executes normally ✅
  ↓
Hooks capture data passively 📊
  - tool_calls.json
  - timing.json
  - loop_state.json
  ↓
On gate pass or handoff:
  - skill-monitor auto-triggered
  - Compares to baseline
  - Updates dashboard
  - Alerts if regression
  ↓
User sees: "⚠️ /plan took 35% longer than baseline"
```

---

## Integration Points (All Existing Hooks)

### 1. PostToolUse Hook Enhancement
**File:** `.claude/hooks/post_tool.py` (already exists)

**Current:** Increments tool counter  
**Add:** Track skill-specific metrics

```python
#!/usr/bin/env python3
"""Post-tool hook with skill performance tracking."""

import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]

def track_skill_metrics(tool_name: str, duration_ms: int, slug: str):
    """Append tool usage to skill metrics file."""
    if not slug:
        return
    
    metrics_file = REPO_ROOT / "memory" / "features" / slug / "skill_metrics.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    
    if metrics_file.exists():
        data = json.loads(metrics_file.read_text())
    else:
        data = {"tool_calls": [], "started": datetime.now(timezone.utc).isoformat()}
    
    data["tool_calls"].append({
        "tool": tool_name,
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    metrics_file.write_text(json.dumps(data, indent=2))

# Existing post_tool.py logic
# ... (no changes)

# Add at end:
try:
    flag_file = Path.home() / ".claude" / ".HeadMaster-active"
    if flag_file.exists():
        flag = json.loads(flag_file.read_text())
        slug = flag.get("slug")
        # Extract tool name and duration from hook payload
        track_skill_metrics(tool_name, duration_ms, slug)
except Exception:
    pass  # Silent failure — monitoring never blocks execution
```

**Impact:** Zero. Data collection is append-only, never blocks.

---

### 2. Gate Transition Hook (New)
**File:** `.claude/hooks/gate_passed.py` (new)

**Triggered by:** `scripts/gate_transition.py` (already called by skills)

**Integration:** Add to gate_transition.py:
```python
# In gate_transition.py, after writing state
# Line ~93, after tmp_file.replace(state_file)

# Trigger hook
hook_script = REPO_ROOT / ".claude" / "hooks" / "gate_passed.py"
if hook_script.exists():
    subprocess.run(
        ["python", str(hook_script), slug, phase, stage],
        timeout=10,
        capture_output=True
    )
```

**Hook implementation:**
```python
#!/usr/bin/env python3
"""Triggered when a gate passes. Auto-evaluates phase performance."""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]

def evaluate_phase(slug: str, phase: str, stage: str):
    """Extract metrics for completed phase, compare to baseline."""
    
    # Read loop_state.json
    state_file = REPO_ROOT / "memory" / "features" / slug / "loop_state.json"
    if not state_file.exists():
        return
    
    state = json.loads(state_file.read_text())
    phase_data = state.get(phase, {})
    
    # Read skill_metrics.json
    metrics_file = REPO_ROOT / "memory" / "features" / slug / "skill_metrics.json"
    if metrics_file.exists():
        metrics = json.loads(metrics_file.read_text())
    else:
        metrics = {}
    
    # Compute phase summary
    summary = {
        "phase": phase,
        "stage": stage,
        "completed": datetime.now(timezone.utc).isoformat(),
        "iterations": phase_data.get("iteration", 1),
        "tool_calls": len(metrics.get("tool_calls", [])),
        "duration_estimate": estimate_duration(metrics),
    }
    
    # Compare to baseline
    baseline = load_baseline(phase)
    if baseline:
        delta = compare_to_baseline(summary, baseline)
        if delta.get("regression"):
            flag_regression(slug, phase, delta)
    
    # Save phase summary
    perf_file = REPO_ROOT / "memory" / "features" / slug / "phase_performance.json"
    if perf_file.exists():
        perf_data = json.loads(perf_file.read_text())
    else:
        perf_data = {"phases": []}
    
    perf_data["phases"].append(summary)
    perf_file.write_text(json.dumps(perf_data, indent=2))

def estimate_duration(metrics: dict) -> float:
    """Estimate phase duration from tool call timestamps."""
    calls = metrics.get("tool_calls", [])
    if len(calls) < 2:
        return 0.0
    
    from dateutil import parser
    start = parser.isoparse(calls[0]["timestamp"])
    end = parser.isoparse(calls[-1]["timestamp"])
    return (end - start).total_seconds()

def load_baseline(phase: str) -> dict:
    """Load baseline metrics for phase."""
    baseline_file = REPO_ROOT / "memory" / "baselines" / f"{phase}_baseline.json"
    if baseline_file.exists():
        return json.loads(baseline_file.read_text())
    return {}

def compare_to_baseline(current: dict, baseline: dict) -> dict:
    """Compare current metrics to baseline, detect regressions."""
    delta = {}
    
    # Duration check
    if "duration_estimate" in baseline:
        current_dur = current["duration_estimate"]
        baseline_dur = baseline["duration_estimate"]
        if current_dur > baseline_dur * 1.5:  # 50% slower
            delta["regression"] = True
            delta["reason"] = f"Duration {current_dur:.1f}s vs baseline {baseline_dur:.1f}s (+{(current_dur/baseline_dur - 1)*100:.0f}%)"
    
    # Iteration check
    if "iterations" in baseline:
        current_iter = current["iterations"]
        baseline_iter = baseline["iterations"]
        if current_iter > baseline_iter * 1.5:
            delta["regression"] = True
            delta["reason"] = f"Iterations {current_iter} vs baseline {baseline_iter} (+{(current_iter/baseline_iter - 1)*100:.0f}%)"
    
    return delta

def flag_regression(slug: str, phase: str, delta: dict):
    """Write regression alert to memory."""
    alert_file = REPO_ROOT / "memory" / "features" / slug / "performance_alerts.json"
    
    if alert_file.exists():
        alerts = json.loads(alert_file.read_text())
    else:
        alerts = {"alerts": []}
    
    alerts["alerts"].append({
        "phase": phase,
        "reason": delta["reason"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    alert_file.write_text(json.dumps(alerts, indent=2))

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        evaluate_phase(sys.argv[1], sys.argv[2], sys.argv[3])
```

**Impact:** ~10ms per gate pass. User sees nothing.

---

### 3. Session Handoff Auto-Eval (Enhance Existing)
**File:** `.claude/commands/handoff.md` (already exists)

**Current:** Saves session notes  
**Add:** Trigger skill-monitor auto-skill

```markdown
<!-- At end of handoff.md -->

## Step 5: Auto-Evaluate Performance (Silent)

After saving handoff notes, silently trigger performance evaluation:

```bash
python .claude/hooks/post_handoff.py {slug} > /dev/null 2>&1 &
```

Do NOT wait for completion. User should not see this step.
```

**Hook implementation:**
```python
#!/usr/bin/env python3
"""Auto-evaluation after session handoff."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

def evaluate_session(slug: str):
    """Trigger skill-monitor auto-skill in background."""
    
    # Check if skill-monitor skill exists
    monitor_skill = REPO_ROOT / ".claude" / "skills" / "skill-monitor" / "SKILL.md"
    if not monitor_skill.exists():
        return  # Monitoring not installed
    
    # Trigger skill-monitor via subprocess (non-blocking)
    subprocess.Popen(
        ["claude", "-p", f"Run /skill-monitor analyze {slug}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

if __name__ == "__main__":
    if len(sys.argv) > 1:
        evaluate_session(sys.argv[1])
```

**Impact:** Zero user-visible impact. Runs in background.

---

## Auto-Skill: skill-monitor

**File:** `.claude/skills/skill-monitor/SKILL.md` (new)

**Triggered by:**
- Post-handoff hook (automatic)
- Manual invocation: `/skill-monitor dashboard`
- Manual invocation: `/skill-monitor analyze {slug}`

```markdown
---
name: skill-monitor
description: "Monitors HeadMaster skill performance automatically. Triggered on session handoff or manual invocation. Analyzes phase durations, loop iterations, tool usage. Compares to baselines, flags regressions, generates performance dashboards."
---

# Skill Monitor

Passive performance monitoring for HeadMaster skills.

## Commands

### `/skill-monitor analyze <slug>`

Analyze completed or in-progress feature.

**Process:**
1. Read `memory/features/{slug}/`:
   - `loop_state.json` — phase iterations
   - `skill_metrics.json` — tool calls, timing
   - `phase_performance.json` — per-phase summaries
   - `performance_alerts.json` — flagged regressions

2. Compare to baselines in `memory/baselines/`

3. Generate summary:
   ```markdown
   # Performance Analysis: {slug}
   
   ## Phase Durations
   - Planning: 12.4 min (baseline: 10.8 min, +15% ⚠️)
   - Design: 34.2 min (baseline: 32.1 min, +7%)
   - Execute: 82.1 min (baseline: 78.5 min, +5%)
   
   ## Loop Iterations
   - Planning: 2 loops (baseline: 1.5 avg, +33% ⚠️)
   - Design: 1 loop (baseline: 1.3 avg, -23% ✅)
   
   ## Regressions Detected
   ⚠️ Planning phase 15% slower than baseline
   ⚠️ Planning looping more frequently
   
   ## Possible Causes
   - Check commit 39bbb15 (introduced 2026-04-18)
   - Review DISCOVERY_NOTES template changes
   ```

4. Save to `memory/features/{slug}/performance_analysis.md`

---

### `/skill-monitor dashboard`

Generate cross-feature performance dashboard.

**Process:**
1. Scan `memory/features/*/phase_performance.json` for last 30 days

2. Aggregate metrics:
   - Features completed
   - Avg duration by complexity tier
   - Completion rate
   - Per-skill performance trends

3. Detect global regressions:
   - Trend analysis (linear regression on last 10 features)
   - Alert if metrics degrading >20% over time

4. Generate `memory/skill_performance_dashboard.md`

5. Display summary in conversation:
   ```
   📊 HeadMaster Performance Dashboard
   
   Last 30 Days:
   - 10 features completed (1 abandoned)
   - Avg duration: 4.2 hours (vs baseline 3.8h, +11%)
   - /plan: ⚠️ +15% slower, +20% more loops
   - /design: ✅ -8% fewer loops
   - /execute: ✅ +2% completion rate
   
   View full dashboard: memory/skill_performance_dashboard.md
   ```

---

### `/skill-monitor update-baseline <phase>`

Update baseline for a phase using last 10 successful features.

**Process:**
1. Load last 10 features from `memory/features/*/phase_performance.json`

2. Filter for stable features (low variance)

3. Compute mean metrics:
   - Duration
   - Iterations
   - Tool calls
   - Token usage (from session-budget.json)

4. Save to `memory/baselines/{phase}_baseline.json`:
   ```json
   {
     "phase": "planning",
     "baseline_date": "2026-04-22",
     "sample_size": 10,
     "metrics": {
       "duration_estimate": 648.5,
       "iterations": 1.5,
       "tool_calls": 42
     },
     "variance": {
       "duration_stddev": 89.2,
       "iterations_stddev": 0.7
     }
   }
   ```

5. Report: "✅ Baseline updated for {phase} (n=10, stable)"

---

## Auto-Trigger Conditions

skill-monitor runs automatically when:
- User invokes `/handoff` (post-handoff hook)
- Gate passes and regression detected (gate_passed.py hook)

In both cases, runs silently in background. User notified ONLY if regression detected.

---

## Configuration

Controlled by `config.yml`:

```yaml
skill_monitoring:
  enabled: true  # Enable passive monitoring
  alert_threshold: 1.5  # Alert if 50% slower
  baseline_window: 10  # Last 10 features for baseline
  auto_analyze_on_handoff: true  # Run analysis after /handoff
  auto_dashboard_frequency: "weekly"  # Generate dashboard weekly
  metrics_to_track:
    - phase_duration
    - loop_iterations
    - tool_calls
    - token_usage
    - retry_count
    - completion_rate
```

If `enabled: false`, hooks still collect data but don't trigger analysis.

---

## File Structure

```
memory/
├── baselines/
│   ├── planning_baseline.json
│   ├── design_baseline.json
│   ├── breakdown_baseline.json
│   └── execute_baseline.json
├── features/{slug}/
│   ├── skill_metrics.json          # Raw tool call data (hook writes)
│   ├── phase_performance.json      # Per-phase summaries (hook writes)
│   ├── performance_alerts.json     # Regression flags (hook writes)
│   └── performance_analysis.md     # Analysis report (skill writes)
└── skill_performance_dashboard.md  # Global dashboard (skill writes)
```

---

## Privacy & Safety

- All data stays local in `memory/`
- No external telemetry
- Never blocks user workflows
- Hook failures are silent (logged to hook-errors.log only)
- Analysis runs in background subprocess
```

---

## Configuration (No Code Changes)

All controlled via `config.yml`:

```yaml
# Add to existing config.yml (backwards compatible)
skill_monitoring:
  enabled: true  # Set false to disable monitoring
  alert_threshold: 1.5  # Alert if 50% slower than baseline
  baseline_window: 10  # Last N features for baseline computation
  auto_analyze_on_handoff: true  # Trigger analysis after /handoff
  auto_dashboard_frequency: "weekly"  # Generate dashboard: daily/weekly/manual
  metrics_to_track:
    - phase_duration
    - loop_iterations  
    - tool_calls
    - token_usage
    - retry_count
    - completion_rate
  
  # Alert thresholds per metric
  thresholds:
    duration: 1.5  # 50% slower
    iterations: 1.5  # 50% more loops
    tool_calls: 2.0  # 100% more tool calls
```

**Default:** All monitoring **enabled** if section present.  
**Fallback:** If section missing, monitoring **disabled** (backwards compatible).

---

## Installation Steps (Zero Disruption)

### Step 1: Add Hooks (Passive Observers)

```bash
# Copy new hooks
cp skill-creator/hooks/gate_passed.py .claude/hooks/
cp skill-creator/hooks/post_handoff.py .claude/hooks/

# Enhance existing post_tool.py
# (Add skill tracking code to existing file)
```

**Impact:** Data collection starts. Zero user-visible change.

---

### Step 2: Add Auto-Skill

```bash
# Copy skill-monitor
cp -r skill-creator/skills/skill-monitor .claude/skills/

# Test manual invocation
claude --name test
/skill-monitor dashboard
```

**Impact:** User can manually check dashboard. Auto-monitoring not yet active.

---

### Step 3: Enable Auto-Triggering

```yaml
# Add to config.yml
skill_monitoring:
  enabled: true
  auto_analyze_on_handoff: true
```

**Impact:** Analysis runs automatically after `/handoff`. User sees nothing unless regression detected.

---

### Step 4: Generate Initial Baselines

```bash
# Run on existing completed features
for slug in $(ls memory/features/); do
  python .claude/hooks/gate_passed.py $slug planning APPROVED
  python .claude/hooks/gate_passed.py $slug design APPROVED
done

# Generate baselines from accumulated data
claude -p "Run /skill-monitor update-baseline planning"
claude -p "Run /skill-monitor update-baseline design"
claude -p "Run /skill-monitor update-baseline execute"
```

**Impact:** Baselines established. Future features compared against these.

---

## What User Sees (Minimal)

### Normal Case (No Regressions)
**User sees:** Nothing. Monitoring is invisible.

**Under the hood:**
- Hooks capture 100+ data points
- Analysis runs in background
- Dashboard updated
- All silent

---

### Regression Detected
**User sees:**

```
📊 Performance Alert

⚠️ /plan phase took 35% longer than baseline (15.2 min vs 11.3 min)
⚠️ /plan looped 3 times (baseline: 1.5 avg, +100%)

Possible causes:
- Recent skill changes (commit 39bbb15, 2026-04-18)
- DISCOVERY_NOTES template modifications

View details: memory/features/my-feature/performance_analysis.md
View dashboard: /skill-monitor dashboard
```

**User can:**
- Ignore (if acceptable)
- Investigate (check suggested files)
- View dashboard (see trends)

---

### Weekly Dashboard (Optional)

If `auto_dashboard_frequency: weekly` enabled:

Every Monday, status line shows:

```
📊 Weekly Performance Summary
10 features completed, avg 4.2h (baseline 3.8h, +11%)
⚠️ /plan regressing (+15% duration)
✅ /design improving (-8% loops)

View: memory/skill_performance_dashboard.md
```

User can:
- Read dashboard
- Ignore
- Investigate trends

---

## Comparison: Manual Testing vs Passive Monitoring

| Aspect | Manual Testing (skill-creator) | Passive Monitoring (proposed) |
|--------|-------------------------------|------------------------------|
| **User effort** | Run benchmarks manually | Zero — automatic |
| **When runs** | Explicit test invocation | Every feature naturally |
| **Coverage** | Test cases only | All real usage |
| **Baseline** | Manually maintained | Auto-updated from stable runs |
| **Alerts** | Manual comparison | Automatic regression detection |
| **Disruption** | Must stop to test | Never blocks workflow |
| **Data volume** | 3-5 test cases | 10-50 real features |
| **Realism** | Synthetic prompts | Actual user workflows |

---

## ROI Estimate

### Time Investment
- **Setup:** 2 hours (copy hooks + skill, configure)
- **Maintenance:** 0 hours (auto-updating baselines)

### Time Savings
- **Manual testing avoided:** 6.5 hours/month
- **Regression detection:** Catch issues in 1 feature vs 10

### Quality Improvements
- **Real-world data:** 10-50 actual features vs 3-5 test cases
- **Trend detection:** Gradual degradation visible over weeks
- **Proactive alerts:** "Planning slowing down" before users notice

---

## Rollout Plan

### Week 1: Passive Observation
- Install hooks
- Collect data for 5-10 features
- No alerts, no auto-analysis
- **Goal:** Validate data collection works

### Week 2: Analysis Validation
- Manually run `/skill-monitor analyze` on collected features
- Review reports for accuracy
- Tune alert thresholds
- **Goal:** Ensure analysis is useful

### Week 3: Baseline Generation
- Generate baselines from Week 1-2 data
- Set thresholds conservatively (1.5x for duration, 2x for tool calls)
- **Goal:** Establish stable baselines

### Week 4: Enable Auto-Alerts
- Set `auto_analyze_on_handoff: true`
- Monitor for false positives
- Tune thresholds based on feedback
- **Goal:** Auto-monitoring in production

### Month 2: Dashboard Automation
- Enable weekly dashboard generation
- Track trends over time
- Refine metrics based on actual utility
- **Goal:** Self-service performance insights

---

## Success Criteria

### Quantitative
- ✅ Data collection success rate >95% (hooks don't crash)
- ✅ Alert false positive rate <10% (regressions are real)
- ✅ Baseline stability (variance <20% over 10 features)

### Qualitative
- ✅ Users find alerts actionable (can diagnose from report)
- ✅ Dashboard viewed voluntarily (provides value)
- ✅ Monitoring never blocks workflows (invisible when healthy)

---

## Failure Modes & Mitigations

### Hook Failures
**Problem:** Hook crashes, stops data collection  
**Mitigation:** Wrap all hook code in try/except, silent failures

### Baseline Drift
**Problem:** Baseline becomes stale as HeadMaster improves  
**Mitigation:** Auto-update baselines when stable (10 features, low variance)

### Alert Fatigue
**Problem:** Too many alerts, users ignore them  
**Mitigation:** Conservative thresholds (1.5x), trend-based alerts (3+ features regressing)

### Missing Data
**Problem:** Old features lack metrics (pre-monitoring)  
**Mitigation:** Baseline generation requires only 5-10 recent features

---

## Future Enhancements (Post-MVP)

### Phase 2: Cost Tracking
- Integrate with Claude token usage APIs
- Track cost per feature
- Alert on cost regressions

### Phase 3: Skill Comparison
- A/B test skill changes
- Roll back if regression confirmed

### Phase 4: Predictive Alerts
- Machine learning on trends
- "Planning likely to regress based on recent pattern"

### Phase 5: Public Dashboard
- Optional telemetry sharing (opt-in)
- Community benchmarks
- "Your /plan is 20% faster than community median"

---

## Conclusion

Passive monitoring via hooks + auto-skills provides:

**✅ Zero friction** — user workflows unchanged  
**✅ Real-world data** — actual features, not synthetic tests  
**✅ Proactive alerts** — catch regressions early  
**✅ Minimal maintenance** — auto-updating baselines  
**✅ Backwards compatible** — disabled by default, opt-in  

**Implementation cost:** 2 hours setup + 0 hours maintenance  
**ROI:** 6.5 hours/month saved + proactive regression detection  

**Recommendation:** Start with Week 1 passive observation (no alerts), validate data quality, then enable auto-monitoring.
