#!/usr/bin/env python3
"""Per-feature metrics collection and cross-feature aggregation.

Append-only JSONL file per feature. No async, no daemon, no external deps.
Called by gate_transition.py and skills at phase boundaries.

Usage:
    # Emit a phase event
    python scripts/metrics.py emit <slug> <event_type> [--phase <phase>] [--stage <stage>] [--verdict <verdict>] [--story <key>] [--extra '<json>']

    # Show metrics for one feature
    python scripts/metrics.py report <slug>

    # Aggregate across all features (used by /navigate dashboard)
    python scripts/metrics.py aggregate

Event types:
    gate_pass     — phase/stage gate passed
    gate_fail     — phase/stage gate failed (review rejection, build failure)
    phase_start   — phase entered
    story_start   — story execution began
    story_complete — story finished (pass or fail)
    story_retry   — story retried after failure
    escalation    — story escalated to human
    feature_complete — feature fully done
"""
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "memory" / "features"
SESSION_FILE = Path.home() / ".claude" / ".HeadMaster-session-budget.json"

VALID_EVENTS = {
    "gate_pass", "gate_fail", "phase_start",
    "story_start", "story_complete", "story_retry",
    "escalation", "feature_complete",
}


def _metrics_path(slug: str) -> Path:
    return MEMORY_DIR / slug / "metrics.jsonl"


def _read_session_budget() -> dict:
    """Snapshot current session budget for token estimation."""
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _append_event(slug: str, event: dict):
    path = _metrics_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")


def _load_events(slug: str) -> list:
    path = _metrics_path(slug)
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def cmd_emit(slug: str, event_type: str, phase: str = None, stage: str = None,
             verdict: str = None, story: str = None, extra: dict = None):
    if event_type not in VALID_EVENTS:
        print(f"[metrics] Unknown event type: {event_type}. Valid: {sorted(VALID_EVENTS)}", file=sys.stderr)
        sys.exit(1)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
    }
    if phase:
        event["phase"] = phase
    if stage:
        event["stage"] = stage
    if verdict:
        event["verdict"] = verdict
    if story:
        event["story"] = story
    if extra:
        event["extra"] = extra

    # Snapshot session budget for token estimation
    budget = _read_session_budget()
    if budget.get("total_tokens"):
        event["session_tokens_est"] = budget["total_tokens"]
    if budget.get("turn_count"):
        event["session_turns"] = budget["turn_count"]

    _append_event(slug, event)
    print(f"[metrics] {slug}: {event_type} {phase or ''}/{stage or ''}", file=sys.stderr)


def cmd_report(slug: str):
    events = _load_events(slug)
    if not events:
        print(json.dumps({"slug": slug, "events": 0, "message": "No metrics recorded"}))
        return

    stats = _compute_feature_stats(slug, events)
    print(json.dumps(stats, indent=2))


def cmd_aggregate():
    if not MEMORY_DIR.is_dir():
        print(json.dumps({"features": 0, "message": "No features found"}))
        return

    features = []
    totals = {
        "features": 0, "stories": 0, "retries": 0, "escalations": 0,
        "gate_failures": 0, "first_pass_stories": 0,
    }

    for slug_dir in sorted(MEMORY_DIR.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        events = _load_events(slug)
        if not events:
            continue

        stats = _compute_feature_stats(slug, events)
        features.append(stats)
        totals["features"] += 1
        totals["stories"] += stats.get("stories_total", 0)
        totals["retries"] += stats.get("retries", 0)
        totals["escalations"] += stats.get("escalations", 0)
        totals["gate_failures"] += stats.get("gate_failures", 0)
        totals["first_pass_stories"] += stats.get("first_pass_stories", 0)

    if totals["stories"] > 0:
        totals["first_pass_rate"] = round(totals["first_pass_stories"] / totals["stories"] * 100, 1)
    else:
        totals["first_pass_rate"] = None

    output = {"totals": totals, "features": features}
    print(json.dumps(output, indent=2))


def _compute_feature_stats(slug: str, events: list) -> dict:
    stats = {
        "slug": slug,
        "events": len(events),
        "stories_total": 0,
        "stories_complete": 0,
        "first_pass_stories": 0,
        "retries": 0,
        "escalations": 0,
        "gate_failures": 0,
        "phases": {},
        "phase_sequence": [],
    }

    # Track per-story retry counts
    story_retries = {}
    story_seen = set()
    story_complete = set()

    # Track phase timing (first event → last event per phase)
    phase_first = {}
    phase_last = {}
    phase_verdicts = {}

    for e in events:
        ev = e.get("event")
        phase = e.get("phase", "unknown")
        story = e.get("story")
        ts = e.get("ts")

        # Phase timing
        if phase != "unknown":
            if phase not in phase_first:
                phase_first[phase] = ts
                stats["phase_sequence"].append(phase)
            phase_last[phase] = ts

        if ev == "gate_pass":
            phase_verdicts.setdefault(phase, []).append("pass")
        elif ev == "gate_fail":
            stats["gate_failures"] += 1
            phase_verdicts.setdefault(phase, []).append("fail")
        elif ev == "story_start":
            if story:
                story_seen.add(story)
        elif ev == "story_complete":
            if story:
                story_complete.add(story)
                if story_retries.get(story, 0) == 0:
                    stats["first_pass_stories"] += 1
        elif ev == "story_retry":
            stats["retries"] += 1
            if story:
                story_retries[story] = story_retries.get(story, 0) + 1
        elif ev == "escalation":
            stats["escalations"] += 1

    stats["stories_total"] = len(story_seen)
    stats["stories_complete"] = len(story_complete)

    if stats["stories_total"] > 0:
        stats["first_pass_rate"] = round(stats["first_pass_stories"] / max(len(story_complete), 1) * 100, 1)
    else:
        stats["first_pass_rate"] = None

    # Phase summary
    for phase in stats["phase_sequence"]:
        p_stats = {
            "passes": phase_verdicts.get(phase, []).count("pass"),
            "failures": phase_verdicts.get(phase, []).count("fail"),
        }
        if phase_first.get(phase) and phase_last.get(phase):
            p_stats["first_event"] = phase_first[phase]
            p_stats["last_event"] = phase_last[phase]
        stats["phases"][phase] = p_stats

    # Token estimate: diff between first and last event's session_tokens_est
    token_estimates = [e.get("session_tokens_est") for e in events if e.get("session_tokens_est")]
    if len(token_estimates) >= 2:
        stats["token_est_total"] = token_estimates[-1] - token_estimates[0]
    elif token_estimates:
        stats["token_est_total"] = token_estimates[-1]

    return stats


def main():
    if len(sys.argv) < 2:
        print("Usage: metrics.py <emit|report|aggregate> [args]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "emit":
        if len(sys.argv) < 4:
            print("Usage: metrics.py emit <slug> <event_type> [options]", file=sys.stderr)
            sys.exit(1)
        slug = sys.argv[2]
        event_type = sys.argv[3]

        # Parse optional flags
        kwargs = {}
        args = sys.argv[4:]
        i = 0
        while i < len(args):
            if args[i] == "--phase" and i + 1 < len(args):
                kwargs["phase"] = args[i + 1]; i += 2
            elif args[i] == "--stage" and i + 1 < len(args):
                kwargs["stage"] = args[i + 1]; i += 2
            elif args[i] == "--verdict" and i + 1 < len(args):
                kwargs["verdict"] = args[i + 1]; i += 2
            elif args[i] == "--story" and i + 1 < len(args):
                kwargs["story"] = args[i + 1]; i += 2
            elif args[i] == "--extra" and i + 1 < len(args):
                try:
                    kwargs["extra"] = json.loads(args[i + 1])
                except json.JSONDecodeError:
                    print(f"[metrics] Invalid JSON for --extra: {args[i + 1]}", file=sys.stderr)
                    sys.exit(1)
                i += 2
            else:
                i += 1

        cmd_emit(slug, event_type, **kwargs)

    elif command == "report":
        if len(sys.argv) < 3:
            print("Usage: metrics.py report <slug>", file=sys.stderr)
            sys.exit(1)
        cmd_report(sys.argv[2])

    elif command == "aggregate":
        cmd_aggregate()

    else:
        print(f"[metrics] Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
