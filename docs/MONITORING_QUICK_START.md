# Skill Monitoring - Quick Start Guide

**Status:** ✅ Phases 1-3 Active (Data Collection + Analysis)  
**Date:** 2026-04-22

---

## What's Running Now

✅ **Phase 1:** Passive observation (deprecated, replaced by Phase 2)  
✅ **Phase 2:** Structured metrics per feature  
✅ **Phase 3:** Gate pass analysis  

🔲 **Phase 4:** Baseline generation (requires data from 3-5 features)  
🔲 **Phase 5:** Regression alerts (after baselines exist)  
🔲 **Phase 6:** Dashboard skill  

---

## How It Works (Invisible to You)

### Every Tool Call
```
You: (use any Claude tool)
  ↓
PostToolUse hook fires
  ↓
skill_metrics_collector.py appends to:
  memory/features/{slug}/skill_metrics.json
  
{
  "feature": "my-feature",
  "tool_calls": [
    {"tool": "Read", "timestamp": "...", "duration_ms": 150},
    {"tool": "Write", "timestamp": "...", "duration_ms": 89}
  ]
}
```

### Every Gate Pass
```
Skill calls: gate_transition.py planning APPROVED
  ↓
Gate hook fires automatically
  ↓
gate_passed.py analyzes phase:
  - Duration: (last tool - first tool)
  - Iterations: from loop_state.json
  - Tool count: len(tool_calls)
  ↓
Writes to: memory/features/{slug}/phase_performance.json

{
  "phases": [
    {
      "phase": "planning",
      "duration_seconds": 742.3,
      "iterations": 2,
      "tool_calls": 87,
      "status": "PASS"
    }
  ]
}
```

---

## What Gets Collected

### Per Feature
```
memory/features/my-feature/
├── skill_metrics.json          # Every tool call with timestamp
├── phase_performance.json      # Summary per phase (after gate)
└── loop_state.json             # (existing - not modified)
```

### Monitoring Logs
```
memory/monitoring-logs/
├── metrics_collection.log      # (Phase 1 only, deprecated)
└── errors.log                  # Hook errors (should be empty)
```

---

## Checking the Data

### View Tool Calls for a Feature
```bash
# See all tool calls
cat memory/features/pwr-es9-migration/skill_metrics.json | jq '.tool_calls'

# Count by tool type
jq -r '.tool_calls[].tool' memory/features/pwr-es9-migration/skill_metrics.json | sort | uniq -c | sort -rn
```

### View Phase Summaries
```bash
# See phase performance
cat memory/features/pwr-es9-migration/phase_performance.json

# Pretty print
jq . memory/features/pwr-es9-migration/phase_performance.json
```

### Check for Errors
```bash
# Should be empty or not exist
cat memory/monitoring-logs/errors.log
```

---

## Zero Impact Guarantee

**Performance:**
- Hook overhead: <1ms per tool call
- Atomic writes: never corrupts files
- Silent failures: never blocks execution

**Validation:**
```bash
# Check hook never times out
grep "timeout" memory/monitoring-logs/errors.log
# (should be empty)

# Verify data collection works
ls memory/features/*/skill_metrics.json
# (should list files)
```

---

## Next Steps (Phase 4-6)

### Phase 4: Baselines (Ready When)
- Need 3-5 completed features with metrics
- Run: `python scripts/generate_baseline.py planning`
- Creates: `memory/baselines/planning_baseline.json`

### Phase 5: Alerts (After Phase 4)
- Adds regression detection to gate_passed.py
- Alerts if 50% slower than baseline
- User sees warning in stderr

### Phase 6: Dashboard (Final)
- Add `/skill-monitor` skill
- Commands: dashboard, analyze, update-baseline
- View trends across features

**Timeline:** Phases 4-6 can be done in 1-2 hours once enough data collected.

---

## Rollback

### Quick Rollback (Any Time)
```bash
# Back to Phase 2 (remove gate analysis)
git checkout 88917d9

# Back to Phase 1 (remove structured metrics)
git checkout 2d7ce73

# Remove monitoring completely
git checkout 0c8ca2d
```

### Git History
```
46e5882 - Phase 3 complete ← CURRENT
2c76f33 - Phase 3 implementation
630b504 - Phase 2 complete
88917d9 - Phase 2 implementation
2d7ce73 - Phase 1 implementation
0c8ca2d - Pre-monitoring checkpoint
```

---

## Troubleshooting

### Hook Not Running?
```bash
# Check settings
grep "skill_metrics_collector" .claude/settings.local.json

# Restart Claude session
# (hooks load at session start)
```

### No Data Collected?
```bash
# Check active feature flag
cat ~/.claude/.HeadMaster-active

# Verify feature directory exists
ls memory/features/
```

### Errors in Log?
```bash
cat memory/monitoring-logs/errors.log

# Common issues:
# - Permission denied: check directory writable
# - Import error: check Python dependencies
# - JSON decode: check file not corrupted
```

---

## Testing

### Quick Smoke Test
```bash
claude --name "test-monitoring"
/navigate
(Esc)

# Check data was collected
tail memory/features/*/skill_metrics.json
```

### Full Test (Use Real Feature)
```bash
claude --name "pwr-es9-migration"
/design pwr-es9-migration

# After gate passes, check:
cat memory/features/pwr-es9-migration/phase_performance.json
```

---

## Configuration

Currently using defaults (no config needed).

**Future** (Phase 5+):
```yaml
# config.yml (will add)
skill_monitoring:
  enabled: true
  alert_threshold: 1.5  # Alert if 50% slower
  baseline_window: 10   # Last 10 features
```

---

## What to Expect

### Now (Phases 1-3)
- **Invisible:** You see nothing
- **Collecting:** Tool calls + phase summaries
- **No alerts:** Just recording data

### After Phase 4 (Baselines)
- **Still invisible:** Data collection same
- **Baseline files:** memory/baselines/*.json
- **Ready for alerts:** But not enabled yet

### After Phase 5 (Alerts)
- **Mostly invisible:** Still silent
- **Alerts if regression:** stderr message
- **Example:** "⚠️ /plan 35% slower than baseline"

### After Phase 6 (Dashboard)
- **Self-service:** `/skill-monitor dashboard`
- **Trends:** See performance over time
- **Analysis:** Per-feature deep dive

---

## Files Modified

```
.claude/hooks/skill_metrics_collector.py  (NEW - Phase 2)
.claude/hooks/gate_passed.py              (NEW - Phase 3)
.claude/settings.local.json               (MODIFIED - added hooks)
scripts/gate_transition.py                (MODIFIED - calls gate_passed.py)
```

All other files unchanged.

---

## Support

**Questions?** Check:
- Full plan: `docs/IMPLEMENTATION_PLAN_MONITORING.md`
- Status: `docs/MONITORING_STATUS.md`
- Design: `docs/PASSIVE_SKILL_MONITORING_DESIGN.md`

**Issues?** Look at:
- Error log: `memory/monitoring-logs/errors.log`
- Git commits: `git log --oneline | head -10`

**Rollback:** `git checkout <commit>` (see Git History above)
