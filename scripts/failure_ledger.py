#!/usr/bin/env python
"""Structured failure ledger for deterministic retry logic.

Maintains an append-only JSON ledger of failed approaches per story,
persisted across /handoff and /clear. The implement phase loads this
before every retry to avoid repeating failed approaches.

Usage:
    # Append a failure record after a failed attempt
    python scripts/failure_ledger.py append <project> <slug> <story-key> --record '<json>'

    # Load all failure records for a story (stdout as JSON)
    python scripts/failure_ledger.py load <project> <slug> <story-key>

    # Check if an approach description is too similar to a prior failure
    python scripts/failure_ledger.py check <project> <slug> <story-key> --approach "description"

    # Clean up ledger after story completes
    python scripts/failure_ledger.py cleanup <project> <slug> <story-key>

Examples:
    python scripts/failure_ledger.py append acme my-feature ACME-123 --record '{"approach":"added null check","error_type":"test_failure","error_summary":"NPE at line 42","files_touched":["UserService.java"],"hypothesis":"mock not configured"}'
    python scripts/failure_ledger.py load acme my-feature ACME-123
    python scripts/failure_ledger.py check acme my-feature ACME-123 --approach "add null check in validate()"
"""
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

def _find_root() -> Path:
    """Find HeadMaster root by walking up to config.yml."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "config.yml").exists():
            return p
        p = p.parent
    raise FileNotFoundError("config.yml not found in any parent directory")

REPO_ROOT = _find_root()


def _ledger_path(project: str, slug: str, story_key: str) -> Path:
    return REPO_ROOT / "memory" / "features" / project / slug / f"failure-ledger-{story_key}.json"


def _load_ledger(project: str, slug: str, story_key: str) -> list:
    path = _ledger_path(project, slug, story_key)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_ledger(project: str, slug: str, story_key: str, records: list):
    path = _ledger_path(project, slug, story_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=2), encoding="utf-8")
    tmp.replace(path)


def cmd_append(project: str, slug: str, story_key: str, record_json: str):
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

    records = _load_ledger(project, slug, story_key)
    attempt = len(records) + 1

    record["story_key"] = story_key
    record["attempt"] = attempt
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    record["excluded_approaches"] = [r["approach"] for r in records] + [record["approach"]]
    record["suggested_alternatives"] = _infer_alternatives(record.get("error_type", ""))

    records.append(record)
    _save_ledger(project, slug, story_key, records)
    print(f"[failure-ledger] Recorded attempt {attempt} for {story_key}", file=sys.stderr)


def cmd_load(project: str, slug: str, story_key: str, last_n: int | None = None):
    """Load failure records for a story.

    last_n: if set, return only the last N records in 'records' field.
    excluded_approaches always contains ALL prior approaches regardless of last_n.
    """
    records = _load_ledger(project, slug, story_key)
    if not records:
        print(json.dumps({"attempts": 0, "records": [], "excluded_approaches": []}))
        return

    excluded = [r["approach"] for r in records]
    display_records = records[-last_n:] if last_n and last_n < len(records) else records
    output = {
        "attempts": len(records),
        "records": display_records,
        "excluded_approaches": excluded,
    }
    print(json.dumps(output, indent=2))


def _infer_alternatives(error_type: str) -> list[str]:
    suggestions = {
        "test_failure":   ["Check test setup/teardown", "Verify mock configuration", "Check test data isolation"],
        "build_failure":  ["Check import order", "Verify dependency exists", "Check for circular imports"],
        "runtime_error":  ["Add null guard", "Check initialization order", "Verify API contract"],
        "timeout":        ["Add async handling", "Check resource cleanup", "Reduce scope of operation"],
        "compilation":    ["Check type annotations", "Verify interface signature", "Check generics/templates"],
    }
    return suggestions.get(error_type, ["Try a structurally different implementation approach"])


def cmd_check(project: str, slug: str, story_key: str, approach: str):
    """Check if a proposed approach overlaps with prior failures.

    Uses simple keyword overlap — not a similarity model.
    Returns exit code 1 if overlap exceeds threshold.
    """
    records = _load_ledger(project, slug, story_key)
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
                "suggested_alternatives": r.get("suggested_alternatives", []),
            }
            print(json.dumps(result, indent=2))
            sys.exit(1)

    print(json.dumps({"similar": False, "reason": "No significant overlap with prior failures"}))


def cmd_summarize(project: str, slug: str, story_key: str) -> None:
    """Print structured summary of failure records for a story."""
    records = _load_ledger(project, slug, story_key)
    if not records:
        print(json.dumps({"attempts": 0, "error_types": {}, "hypotheses": []}))
        return

    error_counts: dict[str, int] = {}
    hypotheses: list[str] = []
    for r in records:
        et = r.get("error_type", "unknown")
        error_counts[et] = error_counts.get(et, 0) + 1
        h = r.get("hypothesis", "").strip()
        if h:
            hypotheses.append(h)

    print(json.dumps({"attempts": len(records), "error_types": error_counts, "hypotheses": hypotheses}, indent=2))


def cmd_cleanup(project: str, slug: str, story_key: str):
    """Delete failure ledger for a completed story."""
    path = _ledger_path(project, slug, story_key)
    if not path.exists():
        print(f"[failure-ledger] No ledger found for {story_key}", file=sys.stderr)
        return

    try:
        path.unlink()
        print(f"[failure-ledger] Deleted ledger for {story_key}", file=sys.stderr)
    except Exception as e:
        print(f"[failure-ledger] Failed to delete ledger: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: failure_ledger.py <append|load|check|cleanup|summarize> <project> <slug> <story-key> [options]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command in ("cleanup", "summarize"):
        if len(sys.argv) < 5:
            print(f"Usage: failure_ledger.py {command} <project> <slug> <story-key>", file=sys.stderr)
            sys.exit(1)
        project = sys.argv[2]
        slug = sys.argv[3]
        story_key = sys.argv[4]
        if command == "cleanup":
            cmd_cleanup(project, slug, story_key)
        else:
            cmd_summarize(project, slug, story_key)
        return

    if len(sys.argv) < 5:
        print("Usage: failure_ledger.py <append|load|check|cleanup|summarize> <project> <slug> <story-key> [options]", file=sys.stderr)
        sys.exit(1)

    project = sys.argv[2]
    slug = sys.argv[3]
    story_key = sys.argv[4]

    if command == "append":
        if "--record" not in sys.argv:
            print("[failure-ledger] --record required for append", file=sys.stderr)
            sys.exit(1)
        idx = sys.argv.index("--record")
        if idx + 1 >= len(sys.argv):
            print("[failure-ledger] --record value missing", file=sys.stderr)
            sys.exit(1)
        cmd_append(project, slug, story_key, sys.argv[idx + 1])

    elif command == "load":
        last_n = None
        if "--last" in sys.argv:
            idx = sys.argv.index("--last")
            try:
                last_n = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                print("[failure-ledger] --last requires an integer value", file=sys.stderr)
                sys.exit(1)
        cmd_load(project, slug, story_key, last_n=last_n)

    elif command == "check":
        if "--approach" not in sys.argv:
            print("[failure-ledger] --approach required for check", file=sys.stderr)
            sys.exit(1)
        idx = sys.argv.index("--approach")
        if idx + 1 >= len(sys.argv):
            print("[failure-ledger] --approach value missing", file=sys.stderr)
            sys.exit(1)
        cmd_check(project, slug, story_key, sys.argv[idx + 1])

    else:
        print(f"[failure-ledger] Unknown command: {command}. Valid: append | load | check | cleanup | summarize", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
