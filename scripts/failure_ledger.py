#!/usr/bin/env python3
"""Structured failure ledger for deterministic retry logic.

Maintains an append-only JSON ledger of failed approaches per story,
persisted across /handoff and /clear. The implement phase loads this
before every retry to avoid repeating failed approaches.

Usage:
    # Append a failure record after a failed attempt
    python scripts/failure_ledger.py append <slug> <story-key> --record '<json>'

    # Load all failure records for a story (stdout as JSON)
    python scripts/failure_ledger.py load <slug> <story-key>

    # Check if an approach description is too similar to a prior failure
    python scripts/failure_ledger.py check <slug> <story-key> --approach "description"

Examples:
    python scripts/failure_ledger.py append my-feature PWRE-123 --record '{"approach":"added null check","error_type":"test_failure","error_summary":"NPE at line 42","files_touched":["UserService.java"],"hypothesis":"mock not configured"}'
    python scripts/failure_ledger.py load my-feature PWRE-123
    python scripts/failure_ledger.py check my-feature PWRE-123 --approach "add null check in validate()"
"""
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ledger_path(slug: str, story_key: str) -> Path:
    return REPO_ROOT / "memory" / "features" / slug / f"failure-ledger-{story_key}.json"


def _load_ledger(slug: str, story_key: str) -> list:
    path = _ledger_path(slug, story_key)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_ledger(slug: str, story_key: str, records: list):
    path = _ledger_path(slug, story_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=2), encoding="utf-8")
    tmp.replace(path)


def cmd_append(slug: str, story_key: str, record_json: str):
    """Append a failure record to the ledger."""
    try:
        record = json.loads(record_json)
    except json.JSONDecodeError as e:
        print(f"[failure-ledger] Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    required = ["approach", "error_type", "error_summary", "files_touched", "hypothesis"]
    missing = [k for k in required if k not in record]
    if missing:
        print(f"[failure-ledger] Missing required fields: {missing}", file=sys.stderr)
        sys.exit(1)

    records = _load_ledger(slug, story_key)
    attempt = len(records) + 1

    record["story_key"] = story_key
    record["attempt"] = attempt
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    # Build cumulative exclusion list from all prior approaches
    record["excluded_approaches"] = [r["approach"] for r in records] + [record["approach"]]

    records.append(record)
    _save_ledger(slug, story_key, records)
    print(f"[failure-ledger] Recorded attempt {attempt} for {story_key}", file=sys.stderr)


def cmd_load(slug: str, story_key: str):
    """Load and print all failure records for a story."""
    records = _load_ledger(slug, story_key)
    if not records:
        print(json.dumps({"attempts": 0, "records": [], "excluded_approaches": []}))
        return

    excluded = [r["approach"] for r in records]
    output = {
        "attempts": len(records),
        "records": records,
        "excluded_approaches": excluded,
    }
    print(json.dumps(output, indent=2))


def cmd_check(slug: str, story_key: str, approach: str):
    """Check if a proposed approach overlaps with prior failures.

    Uses simple keyword overlap — not a similarity model.
    Returns exit code 1 if overlap exceeds threshold.
    """
    records = _load_ledger(slug, story_key)
    if not records:
        print(json.dumps({"similar": False, "reason": "No prior failures"}))
        return

    approach_words = set(approach.lower().split())
    for r in records:
        prior_words = set(r["approach"].lower().split())
        if not approach_words or not prior_words:
            continue
        overlap = len(approach_words & prior_words) / max(len(approach_words), len(prior_words))
        if overlap > 0.7:
            result = {
                "similar": True,
                "matched_attempt": r["attempt"],
                "matched_approach": r["approach"],
                "overlap": round(overlap, 2),
                "reason": f"70%+ word overlap with attempt {r['attempt']}",
            }
            print(json.dumps(result, indent=2))
            sys.exit(1)

    print(json.dumps({"similar": False, "reason": "No significant overlap with prior failures"}))


def main():
    if len(sys.argv) < 4:
        print("Usage: failure_ledger.py <append|load|check> <slug> <story-key> [options]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    slug = sys.argv[2]
    story_key = sys.argv[3]

    if command == "append":
        if "--record" not in sys.argv:
            print("[failure-ledger] --record required for append", file=sys.stderr)
            sys.exit(1)
        idx = sys.argv.index("--record")
        if idx + 1 >= len(sys.argv):
            print("[failure-ledger] --record value missing", file=sys.stderr)
            sys.exit(1)
        cmd_append(slug, story_key, sys.argv[idx + 1])

    elif command == "load":
        cmd_load(slug, story_key)

    elif command == "check":
        if "--approach" not in sys.argv:
            print("[failure-ledger] --approach required for check", file=sys.stderr)
            sys.exit(1)
        idx = sys.argv.index("--approach")
        if idx + 1 >= len(sys.argv):
            print("[failure-ledger] --approach value missing", file=sys.stderr)
            sys.exit(1)
        cmd_check(slug, story_key, sys.argv[idx + 1])

    else:
        print(f"[failure-ledger] Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
