---
name: skill-monitor
description: "Performance monitoring dashboard for HeadMaster skills. Shows phase durations, loop iterations, tool usage, and regressions across features. Use when user asks about performance, wants monitoring dashboard, investigates slowness, or checks skill metrics. Triggers on: 'performance', 'monitoring', 'dashboard', 'how long', 'regression', 'baseline'."
---

# Skill Monitor

Performance analysis and monitoring for HeadMaster.

## Commands

### `/skill-monitor dashboard`

Show performance summary across all features.

**Process:**
1. Scan `memory/features/*/phase_performance.json`
2. Load `memory/baselines/*.json`
3. Aggregate by phase (last 30 days)
4. Calculate trends and detect regressions

**Output format:**
```markdown
# HeadMaster Performance Dashboard

## Summary (Last 30 Days)
- Features analyzed: {N}
- Total development time: {hours}
- Avg per feature: {hours}

## By Phase
| Phase | Avg Duration | Avg Loops | Baseline | Delta | Status |
|-------|--------------|-----------|----------|-------|--------|
| Planning | 12.4 min | 2.1 | 10.8 min | +15% | WARNING |
| Design | 34.2 min | 1.3 | 32.1 min | +7% | OK |
| Execute | 82.1 min | 1.0 | 78.5 min | +5% | OK |

## Recent Regressions
{list of regressions from performance_alerts.json}

## Files
- Dashboard: memory/skill_performance_dashboard.md
- Baselines: memory/baselines/*.json
- Alerts: memory/features/*/performance_alerts.json
```

**Implementation:**
```python
# Read all phase_performance.json files
features = glob("memory/features/*/phase_performance.json")

# Aggregate by phase
from collections import defaultdict
phase_data = defaultdict(list)

for f in features:
    data = json.loads(read(f))
    for phase in data["phases"]:
        phase_data[phase["phase"]].append(phase)

# Calculate stats per phase
for phase, entries in phase_data.items():
    durations = [e["duration_seconds"] for e in entries]
    avg_dur = sum(durations) / len(durations)
    # Compare to baseline...
```

Save output to `memory/skill_performance_dashboard.md`.

---

### `/skill-monitor analyze <slug>`

Detailed analysis for one feature.

**Process:**
1. Read `memory/features/{slug}/phase_performance.json`
2. Read `memory/features/{slug}/performance_alerts.json`
3. Read `memory/features/{slug}/skill_metrics.json`
4. Load baselines for comparison
5. Generate detailed report

**Output format:**
```markdown
# Performance Analysis: {slug}

## Phase Summary
| Phase | Duration | Iterations | Tool Calls | vs Baseline |
|-------|----------|------------|------------|-------------|
| Planning | 15.2 min | 3 | 94 | +35% SLOW |
| Design | 28.1 min | 1 | 132 | -15% FAST |

## Regressions Detected
{detailed regression info}

## Tool Usage
Most used tools:
- Read: 45 calls
- Write: 23 calls
- Bash: 18 calls
- Agent: 8 calls

## Timeline
{chronological view of phases}

## Recommendations
{actionable insights based on data}
```

Save to `memory/features/{slug}/performance_analysis.md`.

---

### `/skill-monitor update-baseline <phase>`

Regenerate baseline from last 10 stable features.

**Process:**
1. Call `python scripts/generate_baseline.py {phase} --window 10`
2. Read generated baseline
3. Report new metrics

**Output:**
```
SUCCESS: Baseline updated for {phase}
Sample size: 10 features
Duration: 648.5s +/- 89.2s
Iterations: 1.6 +/- 0.5
Tool calls: 87.4 +/- 12.3
```

---

### `/skill-monitor list-alerts`

Show all performance alerts across features.

**Process:**
1. Find all `memory/features/*/performance_alerts.json`
2. Parse and aggregate
3. Sort by severity (duration regression > iteration regression)

**Output:**
```markdown
# Performance Alerts

## Critical (50%+ slower)
- pwr-es9-migration: planning 62% slower (2026-04-21)
  Baseline: 10.8 min | Actual: 17.5 min

## Warnings (20-49% slower)
- api-rate-limit: design 35% slower (2026-04-18)
  Baseline: 32.1 min | Actual: 43.3 min

## Info
{other alerts}
```

---

## Helper Functions

```python
def load_all_features():
    """Load performance data from all features."""
    features_dir = Path("memory/features")
    data = {}
    
    for feature_dir in features_dir.iterdir():
        if not feature_dir.is_dir():
            continue
        
        slug = feature_dir.name
        perf_file = feature_dir / "phase_performance.json"
        
        if perf_file.exists():
            data[slug] = json.loads(perf_file.read_text())
    
    return data

def load_baselines():
    """Load all baseline files."""
    baselines_dir = Path("memory/baselines")
    baselines = {}
    
    for baseline_file in baselines_dir.glob("*_baseline.json"):
        phase = baseline_file.stem.replace("_baseline", "")
        baselines[phase] = json.loads(baseline_file.read_text())
    
    return baselines

def calculate_delta(current, baseline):
    """Calculate percentage difference."""
    if baseline == 0:
        return 0
    return ((current / baseline) - 1) * 100
```

---

## Configuration

Reads from `config.yml`:

```yaml
skill_monitoring:
  enabled: true
  alert_threshold: 1.5  # 50% slower triggers alert
  baseline_window: 10   # Last 10 features for baseline
```

If section missing, uses defaults.

---

## Output Files

All generated files saved to `memory/`:

- `memory/skill_performance_dashboard.md` — Global dashboard
- `memory/features/{slug}/performance_analysis.md` — Per-feature analysis

---

## Error Handling

- If no features found → inform user, suggest running features
- If baselines missing → warn, show raw data without comparison
- If performance_alerts.json missing → show "No alerts" (normal)
- All file I/O wrapped in try/except, never crash

---

## Examples

**User:** "Show me the performance dashboard"
→ Trigger: `/skill-monitor dashboard`

**User:** "Why is planning taking so long?"
→ Trigger: `/skill-monitor dashboard`, highlight planning row

**User:** "Analyze pwr-es9-migration performance"
→ Trigger: `/skill-monitor analyze pwr-es9-migration`

**User:** "Update design baseline"
→ Trigger: `/skill-monitor update-baseline design`

---

## Notes

- Dashboard updates on-demand (not auto-generated)
- Analysis is retrospective (after phases complete)
- Baselines updated manually via command
- All data read-only (never modifies phase_performance.json)
