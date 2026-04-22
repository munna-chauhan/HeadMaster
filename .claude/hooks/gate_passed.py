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

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        slug = sys.argv[1]
        phase = sys.argv[2]
        stage = sys.argv[3]
        analyze_phase(slug, phase, stage)
