# Passive Monitoring Implementation Plan

**Objective:** Add skill monitoring safely, incrementally, with validation at each step.

**Principle:** Test small, validate, then proceed. Rollback if anything breaks.

---

## Phase 0: Pre-Flight Checks ✅

### Step 0.1: Backup Current State

```bash
# Backup existing hooks
cp -r .claude/hooks .claude/hooks.backup.$(date +%Y%m%d)

# Backup existing config
cp config.yml config.yml.backup.$(date +%Y%m%d)

# Create git commit (safety net)
git add -A
git commit -m "chore: backup before skill monitoring integration"
```

**Validation:**
```bash
ls -la .claude/hooks.backup.*
ls -la config.yml.backup.*
git log --oneline | head -1
```

Expected: Backup files exist, commit created.

---

### Step 0.2: Verify Current System Works

```bash
# Test current HeadMaster functionality
claude --name "test-pre-monitoring"
```

**Test commands:**
```
/navigate
(Should show dashboard or "no features")

/plan test-monitoring-setup
(Should start planning or ask for description)

Esc (cancel)
```

**Validation:** Current system works normally.

**If fails:** Fix existing issues before proceeding.

---

## Phase 1: Data Collection (Read-Only, Zero Risk) 📊

### Step 1.1: Create Monitoring Directory Structure

```bash
# Create directories for monitoring data
mkdir -p memory/baselines
mkdir -p memory/monitoring-logs

# Test write permissions
touch memory/baselines/.test
rm memory/baselines/.test

echo "✅ Directories created"
```

**Validation:**
```bash
ls -la memory/baselines
ls -la memory/monitoring-logs
```

Expected: Directories exist, writable.

---

### Step 1.2: Add Data Collection Hook (Read-Only Mode)

Create new file: `.claude/hooks/collect_metrics.py`

```python
#!/usr/bin/env python3
"""
Passive metrics collection hook.
Phase 1: OBSERVE ONLY - write to separate log, don't modify anything.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = REPO_ROOT / "memory" / "monitoring-logs" / "metrics_collection.log"

def log_metric(event_type: str, data: dict):
    """Append metric to observation log (Phase 1: observe only)."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "data": data
        }
        
        # Append to log file
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
            
    except Exception as e:
        # Silent failure - never block execution
        error_log = REPO_ROOT / "memory" / "monitoring-logs" / "errors.log"
        try:
            with open(error_log, "a") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()} collect_metrics error: {e}\n")
        except Exception:
            pass  # Even error logging fails silently

def main():
    """Main entry point for hook."""
    try:
        # Read stdin for hook payload
        if not sys.stdin.isatty():
            payload = json.loads(sys.stdin.read())
        else:
            payload = {}
        
        # Extract relevant data
        event_type = payload.get("hookEventName", "unknown")
        
        # Check for active feature
        flag_file = Path.home() / ".claude" / ".HeadMaster-active"
        slug = None
        if flag_file.exists():
            try:
                flag = json.loads(flag_file.read_text())
                slug = flag.get("slug")
            except Exception:
                pass
        
        # Log the observation
        log_metric(event_type, {
            "slug": slug,
            "payload_size": len(str(payload)),
            "has_slug": slug is not None
        })
        
    except Exception as e:
        # Silent failure
        pass

if __name__ == "__main__":
    main()
```

**Validation:**
```bash
# Make executable
chmod +x .claude/hooks/collect_metrics.py

# Test manually
echo '{"hookEventName": "test", "data": "sample"}' | python .claude/hooks/collect_metrics.py

# Check log was created
cat memory/monitoring-logs/metrics_collection.log
```

Expected output:
```json
{"timestamp": "2026-04-22T...", "event": "test", "data": {...}}
```

**If fails:** Fix script before proceeding. Check Python path, permissions.

---

### Step 1.3: Integrate Hook (PostToolUse - Observation Only)

**File:** `.claude/settings.local.json` (create if doesn't exist)

Add hook configuration:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": "python .claude/hooks/collect_metrics.py",
        "description": "Passive metrics collection (observe only)"
      }
    ]
  }
}
```

**Validation:**
```bash
# Start new session
claude --name "test-phase1"

# Run simple command
/navigate

# Exit
Esc

# Check log
tail -5 memory/monitoring-logs/metrics_collection.log
```

Expected: 1+ log entries with PostToolUse events.

**If fails:** Check `.claude/settings.local.json` syntax, hook path.

---

### Step 1.4: Run Real Feature (Observation Mode)

```bash
claude --name "monitoring-test-feature"
```

**Test workflow:**
```
/navigate "Add simple logging to health check endpoint"
(Should start /plan)

(Let it run for 2-3 minutes, then cancel with Esc)
```

**Validation:**
```bash
# Check metrics were collected
wc -l memory/monitoring-logs/metrics_collection.log
# Should have 50+ lines

# Check for errors
cat memory/monitoring-logs/errors.log
# Should be empty or not exist

# Check feature slug was captured
grep -o '"slug":"[^"]*"' memory/monitoring-logs/metrics_collection.log | head -5
```

Expected: Metrics collected, no errors, slug captured.

**If fails:** Review errors.log, fix collect_metrics.py.

---

### Step 1.5: Validate Non-Interference

**Test:** Run a complete feature while collecting metrics.

```bash
# Use pwr-es9-migration (already in progress)
claude --name "pwr-es9-migration"
/navigate pwr-es9-migration
```

**Monitor for issues:**
- Does the session feel slower? (should be <1ms overhead)
- Any hook errors in status line?
- Does /design work normally?

**Validation:**
```bash
# Check hook never blocked execution
grep "timeout" memory/monitoring-logs/errors.log
# Should be empty

# Check overhead is minimal
# (log file should be small, <1MB even after full feature)
du -h memory/monitoring-logs/metrics_collection.log
```

Expected: <100KB file, no timeouts, no noticeable slowdown.

**Decision Point:** If Phase 1 works for 3-5 features without issues → proceed to Phase 2.

**If issues:** Fix before proceeding. Monitoring must be invisible.

---

## Phase 2: Structured Metrics (Still Read-Only) 📈

### Step 2.1: Enhance Data Collection

Create: `.claude/hooks/skill_metrics_collector.py`

```python
#!/usr/bin/env python3
"""
Enhanced metrics collection with structured data.
Phase 2: Write to feature-specific files, but still read-only (no analysis yet).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

def get_active_feature():
    """Get currently active feature slug."""
    flag_file = Path.home() / ".claude" / ".HeadMaster-active"
    if flag_file.exists():
        try:
            flag = json.loads(flag_file.read_text())
            return flag.get("slug")
        except Exception:
            pass
    return None

def append_tool_call(slug: str, tool_name: str, duration_ms: int = 0):
    """Append tool call to feature metrics."""
    if not slug:
        return
    
    try:
        metrics_file = REPO_ROOT / "memory" / "features" / slug / "skill_metrics.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Read existing
        if metrics_file.exists():
            data = json.loads(metrics_file.read_text())
        else:
            data = {
                "feature": slug,
                "started": datetime.now(timezone.utc).isoformat(),
                "tool_calls": []
            }
        
        # Append new call
        data["tool_calls"].append({
            "tool": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms
        })
        
        # Write atomically
        tmp = metrics_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(metrics_file)
        
    except Exception as e:
        # Log error but never block
        error_log = REPO_ROOT / "memory" / "monitoring-logs" / "errors.log"
        try:
            with open(error_log, "a") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()} skill_metrics error: {e}\n")
        except Exception:
            pass

def main():
    """Hook entry point."""
    try:
        # Get tool name from stdin payload
        if not sys.stdin.isatty():
            payload = json.loads(sys.stdin.read())
            tool_name = payload.get("tool_name", "unknown")
            duration_ms = payload.get("duration_ms", 0)
        else:
            # Test mode
            tool_name = sys.argv[1] if len(sys.argv) > 1 else "test"
            duration_ms = 0
        
        slug = get_active_feature()
        if slug:
            append_tool_call(slug, tool_name, duration_ms)
            
    except Exception:
        pass  # Silent failure

if __name__ == "__main__":
    main()
```

**Validation:**
```bash
# Make executable
chmod +x .claude/hooks/skill_metrics_collector.py

# Test manually
echo '{"tool_name": "Read", "duration_ms": 150}' | python .claude/hooks/skill_metrics_collector.py

# Should fail silently (no active feature)
# Try with active feature simulation
mkdir -p memory/features/test-feature
echo '{"slug": "test-feature"}' > ~/.claude/.HeadMaster-active
echo '{"tool_name": "Read", "duration_ms": 150}' | python .claude/hooks/skill_metrics_collector.py

# Check file created
cat memory/features/test-feature/skill_metrics.json
```

Expected:
```json
{
  "feature": "test-feature",
  "started": "2026-04-22T...",
  "tool_calls": [
    {"tool": "Read", "timestamp": "2026-04-22T...", "duration_ms": 150}
  ]
}
```

**If fails:** Debug script, check file permissions.

---

### Step 2.2: Replace Phase 1 Hook with Phase 2

**Edit:** `.claude/settings.local.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": "python .claude/hooks/skill_metrics_collector.py",
        "description": "Structured metrics collection (Phase 2)"
      }
    ]
  }
}
```

**Validation:**
```bash
# Start new feature
claude --name "test-phase2"
/navigate "Add email validation to signup form"

# Let it run for a few minutes, then cancel

# Check structured metrics were created
ls -la memory/features/*/skill_metrics.json
cat memory/features/*/skill_metrics.json | head -20
```

Expected: Structured JSON with tool_calls array.

---

### Step 2.3: Run Full Feature (Phase 2 Active)

**Test:** Use existing pwr-es9-migration

```bash
claude --name "pwr-es9-migration"
/design pwr-es9-migration "Review elasticsearch-datagroup-api TDD"
```

**Validation during execution:**
- Check skill_metrics.json grows over time
- Verify no performance impact
- Ensure no hook errors

**After completion:**
```bash
# Check metrics file
cat memory/features/pwr-es9-migration/skill_metrics.json

# Count tool calls
jq '.tool_calls | length' memory/features/pwr-es9-migration/skill_metrics.json

# Check most used tools
jq -r '.tool_calls[].tool' memory/features/pwr-es9-migration/skill_metrics.json | sort | uniq -c | sort -rn
```

Expected: 50-200 tool calls captured, no errors.

**Decision Point:** If Phase 2 works for 2-3 features → proceed to Phase 3.

---

## Phase 3: Gate Pass Analysis (First Active Component) ⚙️

### Step 3.1: Create Gate Analysis Script

Create: `.claude/hooks/gate_passed.py`

```python
#!/usr/bin/env python3
"""
Triggered when a gate passes. Analyzes phase performance.
Phase 3: First active analysis - generates reports but NO ALERTS yet.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from dateutil import parser

REPO_ROOT = Path(__file__).resolve().parents[2]

def analyze_phase(slug: str, phase: str, stage: str):
    """Analyze completed phase, generate summary."""
    
    try:
        # Read loop_state
        state_file = REPO_ROOT / "memory" / "features" / slug / "loop_state.json"
        if not state_file.exists():
            return
        
        state = json.loads(state_file.read_text())
        phase_data = state.get(phase, {})
        
        # Read metrics
        metrics_file = REPO_ROOT / "memory" / "features" / slug / "skill_metrics.json"
        if not metrics_file.exists():
            return
        
        metrics = json.loads(metrics_file.read_text())
        
        # Calculate phase duration
        tool_calls = metrics.get("tool_calls", [])
        if len(tool_calls) < 2:
            duration = 0
        else:
            start = parser.isoparse(tool_calls[0]["timestamp"])
            end = parser.isoparse(tool_calls[-1]["timestamp"])
            duration = (end - start).total_seconds()
        
        # Generate summary
        summary = {
            "phase": phase,
            "stage": stage,
            "completed": datetime.now(timezone.utc).isoformat(),
            "iterations": phase_data.get("iteration", 1),
            "tool_calls": len(tool_calls),
            "duration_seconds": duration,
            "status": phase_data.get("status", "UNKNOWN")
        }
        
        # Write to phase_performance.json
        perf_file = REPO_ROOT / "memory" / "features" / slug / "phase_performance.json"
        if perf_file.exists():
            perf_data = json.loads(perf_file.read_text())
        else:
            perf_data = {"phases": []}
        
        perf_data["phases"].append(summary)
        
        tmp = perf_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(perf_data, indent=2))
        tmp.replace(perf_file)
        
        # Log success (optional)
        print(f"[gate_passed] {slug}/{phase} analyzed: {duration:.1f}s, {len(tool_calls)} tools", file=sys.stderr)
        
    except Exception as e:
        # Log error but don't block
        error_log = REPO_ROOT / "memory" / "monitoring-logs" / "errors.log"
        try:
            with open(error_log, "a") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()} gate_passed error: {e}\n")
        except Exception:
            pass

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        slug = sys.argv[1]
        phase = sys.argv[2]
        stage = sys.argv[3]
        analyze_phase(slug, phase, stage)
```

**Validation:**
```bash
# Make executable
chmod +x .claude/hooks/gate_passed.py

# Test manually with existing feature
python .claude/hooks/gate_passed.py pwr-es9-migration design Engineer

# Check output file created
cat memory/features/pwr-es9-migration/phase_performance.json
```

Expected:
```json
{
  "phases": [
    {
      "phase": "design",
      "stage": "Engineer",
      "completed": "2026-04-22T...",
      "iterations": 3,
      "tool_calls": 142,
      "duration_seconds": 1847.3,
      "status": "IN_PROGRESS"
    }
  ]
}
```

**If fails:** Check dateutil installed (`pip install python-dateutil`), fix script.

---

### Step 3.2: Integrate Gate Hook into gate_transition.py

**Edit:** `scripts/gate_transition.py` (ADD at end of main(), after line 93)

```python
    # ... existing code ...
    tmp_file.replace(state_file)

    print(f"[gate] {slug}: {phase}/{stage}", file=sys.stderr)

    # NEW: Trigger gate analysis hook (Phase 3)
    try:
        hook_script = REPO_ROOT / ".claude" / "hooks" / "gate_passed.py"
        if hook_script.exists():
            import subprocess
            subprocess.run(
                ["python", str(hook_script), slug, phase, stage],
                timeout=10,
                capture_output=True
            )
    except Exception:
        pass  # Silent failure - never block gate transition

if __name__ == "__main__":
    main()
```

**Validation:**
```bash
# Test gate transition manually
python scripts/gate_transition.py pwr-es9-migration design Engineer

# Check hook was triggered
ls -la memory/features/pwr-es9-migration/phase_performance.json

# Verify gate still works if hook fails
mv .claude/hooks/gate_passed.py .claude/hooks/gate_passed.py.disabled
python scripts/gate_transition.py pwr-es9-migration design Review
# Should succeed without error

# Re-enable hook
mv .claude/hooks/gate_passed.py.disabled .claude/hooks/gate_passed.py
```

Expected: Gate transition works regardless of hook status.

---

### Step 3.3: Test with Real Gate Pass

```bash
# Continue pwr-es9-migration
claude --name "pwr-es9-migration"
/design pwr-es9-migration
```

**Let skill complete a stage**, then check:

```bash
# Monitor for gate pass
tail -f memory/features/pwr-es9-migration/loop_state.json
# (Wait for pipeline.stage to change)

# Check phase_performance.json was updated
cat memory/features/pwr-es9-migration/phase_performance.json
```

Expected: New entry appears after gate pass, no errors.

**Decision Point:** If Phase 3 works for 2-3 gate passes → proceed to Phase 4.

---

## Phase 4: Baseline Generation (Preparation for Alerts) 📊

### Step 4.1: Create Baseline Generator Script

Create: `scripts/generate_baseline.py`

```python
#!/usr/bin/env python3
"""Generate baseline from recent stable features."""

import argparse
import json
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def collect_phase_data(phase: str, window: int = 10):
    """Collect phase performance from last N features."""
    
    features_dir = REPO_ROOT / "memory" / "features"
    phase_data = []
    
    for feature_dir in features_dir.iterdir():
        if not feature_dir.is_dir():
            continue
        
        perf_file = feature_dir / "phase_performance.json"
        if not perf_file.exists():
            continue
        
        try:
            perf = json.loads(perf_file.read_text())
            for entry in perf.get("phases", []):
                if entry.get("phase") == phase and entry.get("status") == "PASS":
                    phase_data.append(entry)
        except Exception:
            continue
    
    # Sort by completed date, take last N
    phase_data.sort(key=lambda x: x.get("completed", ""))
    return phase_data[-window:]

def generate_baseline(phase: str, window: int = 10):
    """Generate baseline for a phase."""
    
    data = collect_phase_data(phase, window)
    
    if len(data) < 3:
        print(f"⚠️  Not enough data for {phase} (need 3+, have {len(data)})")
        return None
    
    # Extract metrics
    durations = [d["duration_seconds"] for d in data if d["duration_seconds"] > 0]
    iterations = [d["iterations"] for d in data]
    tool_calls = [d["tool_calls"] for d in data]
    
    if not durations:
        print(f"⚠️  No valid durations for {phase}")
        return None
    
    # Calculate baseline
    baseline = {
        "phase": phase,
        "generated": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(data),
        "metrics": {
            "duration_seconds": {
                "mean": statistics.mean(durations),
                "median": statistics.median(durations),
                "stdev": statistics.stdev(durations) if len(durations) > 1 else 0
            },
            "iterations": {
                "mean": statistics.mean(iterations),
                "median": statistics.median(iterations),
                "stdev": statistics.stdev(iterations) if len(iterations) > 1 else 0
            },
            "tool_calls": {
                "mean": statistics.mean(tool_calls),
                "median": statistics.median(tool_calls),
                "stdev": statistics.stdev(tool_calls) if len(tool_calls) > 1 else 0
            }
        }
    }
    
    return baseline

def main():
    parser = argparse.ArgumentParser(description="Generate performance baseline")
    parser.add_argument("phase", help="Phase name (planning, design, execute)")
    parser.add_argument("--window", type=int, default=10, help="Number of features to include")
    args = parser.parse_args()
    
    baseline = generate_baseline(args.phase, args.window)
    
    if baseline:
        # Save baseline
        baseline_file = REPO_ROOT / "memory" / "baselines" / f"{args.phase}_baseline.json"
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text(json.dumps(baseline, indent=2))
        
        print(f"✅ Baseline generated for {args.phase}")
        print(f"   Sample size: {baseline['sample_size']}")
        print(f"   Duration: {baseline['metrics']['duration_seconds']['mean']:.1f}s ± {baseline['metrics']['duration_seconds']['stdev']:.1f}s")
        print(f"   Saved to: {baseline_file}")
    else:
        print(f"❌ Failed to generate baseline for {args.phase}")

if __name__ == "__main__":
    from datetime import datetime, timezone
    main()
```

**Validation:**
```bash
# Make executable
chmod +x scripts/generate_baseline.py

# Try to generate baseline (may fail if not enough data yet)
python scripts/generate_baseline.py design --window 5

# Check if baseline created
ls -la memory/baselines/
cat memory/baselines/design_baseline.json
```

Expected (if enough data):
```json
{
  "phase": "design",
  "generated": "2026-04-22T...",
  "sample_size": 5,
  "metrics": {
    "duration_seconds": {"mean": 1847.3, "median": 1820.0, "stdev": 234.5},
    "iterations": {"mean": 2.2, "median": 2.0, "stdev": 0.8},
    "tool_calls": {"mean": 142.4, "median": 138.0, "stdev": 18.3}
  }
}
```

**If not enough data:** Run 3-5 more features with Phase 2+3 active, then retry.

---

### Step 4.2: Generate All Baselines

```bash
# Generate baselines for all phases (if enough data)
python scripts/generate_baseline.py planning
python scripts/generate_baseline.py design  
python scripts/generate_baseline.py execute

# Review generated baselines
for f in memory/baselines/*_baseline.json; do
  echo "=== $f ==="
  jq '.phase, .sample_size, .metrics.duration_seconds.mean' "$f"
done
```

**Decision Point:** Need 3+ samples per phase to proceed to Phase 5.

**If insufficient data:** Continue running features for 1-2 weeks, collecting metrics in background.

---

## Phase 5: Alerts (Final Active Component) 🚨

### Step 5.1: Add Regression Detection to gate_passed.py

**Edit:** `.claude/hooks/gate_passed.py` (add comparison logic)

```python
# Add after summary generation (around line 50)

        # Phase 3: Generate summary (existing code)
        summary = {...}
        
        # PHASE 5: Compare to baseline (NEW)
        baseline = load_baseline(phase)
        regression = None
        
        if baseline:
            regression = check_regression(summary, baseline)
            if regression:
                flag_regression(slug, phase, regression)
        
        # ... rest of existing code ...

def load_baseline(phase: str) -> dict:
    """Load baseline for phase."""
    baseline_file = REPO_ROOT / "memory" / "baselines" / f"{phase}_baseline.json"
    if baseline_file.exists():
        try:
            return json.loads(baseline_file.read_text())
        except Exception:
            pass
    return {}

def check_regression(current: dict, baseline: dict) -> dict:
    """Check if current performance regressed vs baseline."""
    
    regression = {}
    metrics = baseline.get("metrics", {})
    
    # Duration check
    if "duration_seconds" in metrics:
        curr_dur = current["duration_seconds"]
        base_dur = metrics["duration_seconds"]["mean"]
        
        if curr_dur > base_dur * 1.5:  # 50% slower
            regression["duration"] = {
                "current": curr_dur,
                "baseline": base_dur,
                "delta_pct": ((curr_dur / base_dur) - 1) * 100
            }
    
    # Iteration check
    if "iterations" in metrics:
        curr_iter = current["iterations"]
        base_iter = metrics["iterations"]["mean"]
        
        if curr_iter > base_iter * 1.5:  # 50% more loops
            regression["iterations"] = {
                "current": curr_iter,
                "baseline": base_iter,
                "delta_pct": ((curr_iter / base_iter) - 1) * 100
            }
    
    return regression if regression else None

def flag_regression(slug: str, phase: str, regression: dict):
    """Write regression alert."""
    
    alert_file = REPO_ROOT / "memory" / "features" / slug / "performance_alerts.json"
    
    if alert_file.exists():
        alerts = json.loads(alert_file.read_text())
    else:
        alerts = {"alerts": []}
    
    alert = {
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regression": regression
    }
    
    alerts["alerts"].append(alert)
    
    tmp = alert_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(alerts, indent=2))
    tmp.replace(alert_file)
    
    # Log to stderr (visible in status line)
    print(f"⚠️  Performance regression in {phase}:", file=sys.stderr)
    if "duration" in regression:
        print(f"   Duration: {regression['duration']['delta_pct']:.0f}% slower", file=sys.stderr)
    if "iterations" in regression:
        print(f"   Iterations: {regression['iterations']['delta_pct']:.0f}% more loops", file=sys.stderr)
```

**Validation:**
```bash
# Test regression detection manually
# (Temporarily lower threshold to force alert)

# Edit gate_passed.py: change 1.5 to 1.01 (triggers on 1% increase)
# Run gate pass
python .claude/hooks/gate_passed.py pwr-es9-migration design Engineer

# Check alert was created
cat memory/features/pwr-es9-migration/performance_alerts.json

# Restore threshold to 1.5
```

Expected: Alert JSON created when threshold exceeded.

---

### Step 5.2: Test Regression Alert in Real Workflow

```bash
# Run a phase that might regress
claude --name "pwr-es9-migration"
/design pwr-es9-migration
```

**Watch for:** Alert in stderr if regression detected.

**After completion:**
```bash
# Check for alerts
ls -la memory/features/*/performance_alerts.json
cat memory/features/pwr-es9-migration/performance_alerts.json
```

---

### Step 5.3: Add Configuration

**Edit:** `config.yml` (add at end)

```yaml
# Passive Skill Monitoring (Phase 5)
skill_monitoring:
  enabled: true
  alert_threshold: 1.5  # Alert if 50% slower
  baseline_window: 10  # Last 10 features for baseline
  auto_analyze_on_handoff: false  # Not yet implemented
  metrics_to_track:
    - phase_duration
    - loop_iterations
    - tool_calls
```

**Validation:**
```bash
# Verify valid YAML
python -c "import yaml; yaml.safe_load(open('config.yml'))"
echo "✅ config.yml valid"
```

---

## Phase 6: skill-monitor Auto-Skill (Dashboard & Analysis) 📊

### Step 6.1: Create skill-monitor Skill

Create: `.claude/skills/skill-monitor/SKILL.md`

```markdown
---
name: skill-monitor
description: "Performance monitoring dashboard for HeadMaster. Shows phase durations, loop iterations, regressions across features. Use when user asks about performance, wants to see monitoring dashboard, or investigate why a phase is slow."
---

# Skill Monitor

Performance analysis for HeadMaster features.

## Commands

### `/skill-monitor dashboard`

Show performance summary across all features.

**Process:**
1. Scan `memory/features/*/phase_performance.json`
2. Aggregate by phase (last 30 days)
3. Show summary:
   - Features completed
   - Avg duration by phase
   - Recent regressions
   - Trend over time

**Output format:**
```markdown
# HeadMaster Performance Dashboard

## Summary (Last 30 Days)
- Features completed: 10 (1 abandoned)
- Total development time: 42.3 hours
- Avg per feature: 4.2 hours

## By Phase
| Phase | Avg Duration | Avg Loops | Baseline | Delta |
|-------|--------------|-----------|----------|-------|
| Planning | 12.4 min | 2.1 | 10.8 min | +15% ⚠️ |
| Design | 34.2 min | 1.3 | 32.1 min | +7% |
| Execute | 82.1 min | 1.0 | 78.5 min | +5% |

## Recent Regressions
⚠️ pwr-es9-migration: planning 35% slower (2026-04-21)
⚠️ api-rate-limit: design looped 3x vs 1.5x baseline (2026-04-18)

## Files
- Dashboard: memory/skill_performance_dashboard.md
- Baselines: memory/baselines/*.json
```

---

### `/skill-monitor analyze <slug>`

Detailed analysis for one feature.

**Process:**
1. Read `memory/features/{slug}/phase_performance.json`
2. Read `memory/features/{slug}/performance_alerts.json`
3. Compare to baselines
4. Generate detailed report

**Output:** Write to `memory/features/{slug}/performance_analysis.md`

---

### `/skill-monitor update-baseline <phase>`

Regenerate baseline from last 10 stable features.

**Process:**
1. Call `python scripts/generate_baseline.py {phase}`
2. Report new baseline metrics

---

## Auto-Trigger (Not Yet Implemented)

Future: Trigger automatically after `/handoff` if enabled in config.
```

**Validation:**
```bash
# Test skill manually
claude --name "test-skill-monitor"
/skill-monitor dashboard
```

Expected: Dashboard generated showing features data.

---

## Phase 7: Finalization & Documentation 📝

### Step 7.1: Create Rollback Script

Create: `scripts/disable_monitoring.sh`

```bash
#!/bin/bash
# Disable monitoring and restore original state

echo "Disabling skill monitoring..."

# Remove hooks from settings
if [ -f .claude/settings.local.json ]; then
  mv .claude/settings.local.json .claude/settings.local.json.monitoring-backup
  echo "✅ Hooks disabled"
fi

# Remove monitoring data (optional - uncomment to delete)
# rm -rf memory/baselines
# rm -rf memory/monitoring-logs
# rm memory/features/*/skill_metrics.json
# rm memory/features/*/phase_performance.json
# rm memory/features/*/performance_alerts.json

echo "✅ Monitoring disabled (data preserved)"
echo "To re-enable: restore .claude/settings.local.json.monitoring-backup"
```

**Validation:**
```bash
chmod +x scripts/disable_monitoring.sh
# Don't run yet - just verify it exists
```

---

### Step 7.2: Update Documentation

Update: `README.md` (add section)

```markdown
## Performance Monitoring

HeadMaster includes passive performance monitoring:
- Tracks phase durations, loop iterations, tool usage
- Compares to baselines, alerts on regressions
- Zero user friction (runs in background)

**View dashboard:**
```bash
claude -p "/skill-monitor dashboard"
```

**Configuration:** See `config.yml` → `skill_monitoring` section.

**Disable:** Run `scripts/disable_monitoring.sh`
```

---

### Step 7.3: Final Validation Checklist

```bash
# ✅ All hooks installed and working
ls -la .claude/hooks/collect_metrics.py
ls -la .claude/hooks/skill_metrics_collector.py
ls -la .claude/hooks/gate_passed.py

# ✅ Scripts exist
ls -la scripts/generate_baseline.py
ls -la scripts/disable_monitoring.sh

# ✅ Skill installed
ls -la .claude/skills/skill-monitor/SKILL.md

# ✅ Baselines generated
ls -la memory/baselines/*.json

# ✅ Config updated
grep "skill_monitoring" config.yml

# ✅ No errors in last 3 features
cat memory/monitoring-logs/errors.log | tail -20
```

---

## Rollback Procedures

### If Phase 1 Fails
```bash
rm -rf memory/monitoring-logs
rm .claude/hooks/collect_metrics.py
# Restore settings.local.json from backup
```

### If Phase 2 Fails
```bash
rm -rf memory/features/*/skill_metrics.json
rm .claude/hooks/skill_metrics_collector.py
# Revert to Phase 1 hook
```

### If Phase 3 Fails
```bash
rm -rf memory/features/*/phase_performance.json
# Revert gate_transition.py from git
git checkout scripts/gate_transition.py
```

### If Phase 5 Fails (Alerts)
```bash
# Disable alerts in gate_passed.py
# Comment out regression detection section
# Or reduce threshold to 10.0 (effectively disable)
```

### Complete Rollback
```bash
bash scripts/disable_monitoring.sh
git checkout .claude/hooks/
git checkout scripts/gate_transition.py
git checkout config.yml
rm -rf memory/baselines
rm -rf memory/monitoring-logs
```

---

## Success Criteria

After full rollout:
- ✅ Data collection succeeds >95% (no hook crashes)
- ✅ No performance impact (<10ms overhead per tool call)
- ✅ Baselines stable (variance <30% over 10 features)
- ✅ Alerts actionable (false positive rate <10%)
- ✅ Dashboard provides value (users view voluntarily)
- ✅ Monitoring never blocks workflows

---

## Timeline

**Aggressive:** 1 week (if all phases work first try)
**Realistic:** 2-3 weeks (with validation between phases)
**Conservative:** 4 weeks (wait for 10+ features per phase)

**Recommended:** Conservative approach.
- Week 1: Phase 1-2 (data collection only)
- Week 2-3: Accumulate data from real features
- Week 3: Phase 3-4 (analysis + baselines)
- Week 4: Phase 5-6 (alerts + dashboard)

---

## Next Steps

1. **Review this plan** — understand each phase
2. **Start Phase 0** — backup everything
3. **Execute Phase 1** — passive observation only
4. **Validate thoroughly** — 3-5 features before Phase 2
5. **Proceed incrementally** — don't rush

Good luck! 🚀
