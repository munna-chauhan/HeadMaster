#!/usr/bin/env python3
"""
Triggered when a gate passes. Analyzes phase performance.
Phase 3: Generates summaries but NO ALERTS yet (Phase 5).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

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

        # Calculate phase duration from tool timestamps
        tool_calls = metrics.get("tool_calls", [])
        duration = 0
        if len(tool_calls) >= 2:
            try:
                from dateutil import parser as date_parser
                start = date_parser.isoparse(tool_calls[0]["timestamp"])
                end = date_parser.isoparse(tool_calls[-1]["timestamp"])
                duration = (end - start).total_seconds()
            except Exception:
                # If dateutil not available, estimate from count
                duration = len(tool_calls) * 2  # Rough estimate: 2s per tool call

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

        # Phase 5: Check for regressions
        baseline = load_baseline(phase)
        regression = None

        if baseline:
            regression = check_regression(summary, baseline)
            if regression:
                flag_regression(slug, phase, regression)

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

        # Log success to stderr (visible if needed for debugging)
        print(f"[gate_passed] {slug}/{phase}: {duration:.1f}s, {len(tool_calls)} tools, {summary['iterations']} iterations", file=sys.stderr)

    except Exception as e:
        # Log error but don't block
        error_log = REPO_ROOT / "memory" / "monitoring-logs" / "errors.log"
        try:
            with open(error_log, "a") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()} gate_passed error: {e}\n")
        except Exception:
            pass

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

    # Log to stderr (visible to user)
    print(f"\nWARNING: Performance regression in {phase}:", file=sys.stderr)
    if "duration" in regression:
        print(f"   Duration: {regression['duration']['delta_pct']:.0f}% slower than baseline", file=sys.stderr)
    if "iterations" in regression:
        print(f"   Iterations: {regression['iterations']['delta_pct']:.0f}% more loops than baseline", file=sys.stderr)
    print(f"   View: memory/features/{slug}/performance_alerts.json\n", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        slug = sys.argv[1]
        phase = sys.argv[2]
        stage = sys.argv[3]
        analyze_phase(slug, phase, stage)
