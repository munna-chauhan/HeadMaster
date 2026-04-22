#!/usr/bin/env python3
"""Generate baseline from recent stable features."""

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def collect_phase_data(phase: str, window: int = 10):
    """Collect phase performance from last N features."""

    features_dir = REPO_ROOT / "memory" / "features"
    if not features_dir.exists():
        return []

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
                if entry.get("phase") == phase and entry.get("status") in ("PASS", "IN_PROGRESS", "APPROVED"):
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
        print(f"WARNING: Not enough data for {phase} (need 3+, have {len(data)})")
        print(f"   Tip: Run 3+ features with Phase 3 active to collect data")
        return None

    # Extract metrics
    durations = [d["duration_seconds"] for d in data if d["duration_seconds"] > 0]
    iterations = [d["iterations"] for d in data]
    tool_calls = [d["tool_calls"] for d in data]

    if not durations:
        print(f"WARNING: No valid durations for {phase}")
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
    parser.add_argument("phase", help="Phase name (planning, design, breakdown, execute)")
    parser.add_argument("--window", type=int, default=10, help="Number of features to include")
    args = parser.parse_args()

    baseline = generate_baseline(args.phase, args.window)

    if baseline:
        # Save baseline
        baseline_file = REPO_ROOT / "memory" / "baselines" / f"{args.phase}_baseline.json"
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text(json.dumps(baseline, indent=2))

        print(f"SUCCESS: Baseline generated for {args.phase}")
        print(f"   Sample size: {baseline['sample_size']}")
        print(f"   Duration: {baseline['metrics']['duration_seconds']['mean']:.1f}s +/- {baseline['metrics']['duration_seconds']['stdev']:.1f}s")
        print(f"   Iterations: {baseline['metrics']['iterations']['mean']:.1f} +/- {baseline['metrics']['iterations']['stdev']:.1f}")
        print(f"   Saved to: {baseline_file}")
    else:
        print(f"FAILED: Could not generate baseline for {args.phase}")
        return 1

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
