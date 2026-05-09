#!/usr/bin/env python
"""Convergence checker for review loops. Detects oscillation and recurrence.

Usage:
    python scripts/convergence_check.py <project> <slug> <phase> --blocker-type <type> --findings '<json_array>'

Returns exit code:
    0 — safe to continue loop
    1 — escalate immediately (recurrence or oscillation detected)
    2 — usage error

Stdout: JSON with verdict and reason.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_utils import ConfigResolver
import file_lock

REPO_ROOT = Path(__file__).resolve().parents[1]


STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "not", "for", "in", "of", "to", "and", "or", "it", "this",
    "that", "with", "has", "have", "had", "but", "from", "on",
}


def _blocker_id(finding: dict) -> str:
    """Stable ID using word-overlap normalization.

    Prevents the same blocker described with different wording from being
    treated as a new issue. Lowercases, removes stop words, sorts remaining
    words, then hashes.
    """
    raw = f"{finding.get('section', '')} {finding.get('issue', '')[:80]}"
    words = sorted(set(raw.lower().split()) - STOP_WORDS)
    return "B-" + hashlib.sha256(" ".join(words).encode()).hexdigest()[:6]


def _load_state_locked(project: str, slug: str) -> tuple[dict, object]:
    """Load state with exclusive lock. Returns (state, lock_file)."""
    path = REPO_ROOT / "memory" / "features" / project / slug / "loop_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    # Open file for read+write, create if doesn't exist
    lock_file = open(path, 'a+', encoding="utf-8")
    file_lock.acquire(lock_file)

    lock_file.seek(0)
    content = lock_file.read()

    if content:
        try:
            state = json.loads(content)
        except json.JSONDecodeError:
            state = {}
    else:
        state = {}

    return state, lock_file


def _save_state_locked(lock_file, state: dict):
    """Save state using locked file handle."""
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(json.dumps(state, indent=2))
    lock_file.flush()
    file_lock.release(lock_file)
    lock_file.close()


def check_convergence(project: str, slug: str, phase: str, blocker_type: str,
                      findings: list, max_loops: int = 3) -> dict:
    """Check if loop is converging. Updates blocker_history in state.

    Returns dict: {"verdict": "continue"|"escalate", "reason": str, "iteration": int}

    Note: Uses file locking (Sprint 5 #34) to prevent race conditions during
    read-modify-write. Issue #51 duplicate — confirmed resolved.
    """
    state, lock_file = _load_state_locked(project, slug)
    phase_state = state.setdefault(phase, {})

    iteration = phase_state.get("iteration", 0) + 1
    history = phase_state.setdefault("blocker_history", [])
    stage_visits = phase_state.setdefault("stage_visits", {})

    # Track stage visit count
    target_stage = "Discover" if blocker_type == "DISCOVERY_GAP" else "Draft"
    if phase == "design":
        target_stage = "Architect" if blocker_type == "DESIGN_GAP" else "Engineer"
    stage_visits[target_stage] = stage_visits.get(target_stage, 0) + 1
    stage_visits["Review"] = stage_visits.get("Review", 0) + 1

    # Check 1: Stage visited too many times
    if stage_visits.get(target_stage, 0) > max_loops:
        reason = f"Stage '{target_stage}' visited {stage_visits[target_stage]} times (max {max_loops})"
        _update_state_locked(lock_file, state, phase, iteration, blocker_type, findings, history, stage_visits)
        return {"verdict": "escalate", "reason": reason, "iteration": iteration}

    # Check 2: Recurrence — same blocker appeared, was "resolved", and is back
    recurred = []
    new_ids = set()
    for f in findings:
        bid = _blocker_id(f)
        new_ids.add(bid)
        for h in history:
            if h["id"] == bid and h.get("resolved_iteration") is not None:
                recurred.append(h)

    if recurred:
        summaries = [h["summary"] for h in recurred]
        reason = f"Recurrent blockers (previously resolved, now back): {summaries}"
        _update_state_locked(lock_file, state, phase, iteration, blocker_type, findings, history, stage_visits)
        return {"verdict": "escalate", "reason": reason, "iteration": iteration}

    # Check 3: Standard iteration cap
    if iteration > max_loops:
        reason = f"Max loops ({max_loops}) exceeded"
        _update_state_locked(lock_file, state, phase, iteration, blocker_type, findings, history, stage_visits)
        return {"verdict": "escalate", "reason": reason, "iteration": iteration}

    # Mark previously-open blockers NOT in current findings as resolved
    for h in history:
        if h["id"] not in new_ids and h.get("resolved_iteration") is None:
            h["resolved_iteration"] = iteration

    # Add new blockers to history
    existing_ids = {h["id"] for h in history}
    for f in findings:
        bid = _blocker_id(f)
        if bid in existing_ids:
            # Update appeared_iterations
            for h in history:
                if h["id"] == bid:
                    if iteration not in h["appeared_iterations"]:
                        h["appeared_iterations"].append(iteration)
                    h["resolved_iteration"] = None  # re-opened
        else:
            history.append({
                "id": bid,
                "section": f.get("section", ""),
                "type": blocker_type,
                "summary": f.get("issue", "")[:80],
                "appeared_iterations": [iteration],
                "resolved_iteration": None,
            })

    _update_state_locked(lock_file, state, phase, iteration, blocker_type, findings, history, stage_visits)
    return {"verdict": "continue", "reason": "Converging — no recurrence detected", "iteration": iteration}


def _update_state_locked(lock_file, state, phase, iteration, blocker_type, findings, history, stage_visits):
    state[phase] = {
        "iteration": iteration,
        "last_blocker_type": blocker_type,
        "last_stage": "Review",
        "status": "IN_PROGRESS",
        "findings": findings,
        "blocker_history": history,
        "stage_visits": stage_visits,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _save_state_locked(lock_file, state)


def main():
    if len(sys.argv) < 5:
        print("Usage: convergence_check.py <project> <slug> <phase> --blocker-type <type> --findings '<json>'",
              file=sys.stderr)
        sys.exit(2)

    project = sys.argv[1]
    slug = sys.argv[2]
    phase = sys.argv[3]

    config = ConfigResolver()
    # Per-phase cap overrides global max_loops
    max_loops = (
        config.get(f'pipeline.loop_caps.{phase}', default=None)
        or config.get('pipeline.max_loops', default=3)
    )

    blocker_type = None
    findings = []

    args = sys.argv[4:]
    i = 0
    while i < len(args):
        if args[i] == "--blocker-type" and i + 1 < len(args):
            blocker_type = args[i + 1]; i += 2
        elif args[i] == "--findings" and i + 1 < len(args):
            try:
                findings = json.loads(args[i + 1])
            except json.JSONDecodeError:
                print(f"Invalid JSON for --findings", file=sys.stderr)
                sys.exit(2)
            i += 2
        elif args[i] == "--max-loops" and i + 1 < len(args):
            max_loops = int(args[i + 1]); i += 2
        else:
            i += 1

    if not blocker_type:
        print("--blocker-type required", file=sys.stderr)
        sys.exit(2)

    result = check_convergence(project, slug, phase, blocker_type, findings, max_loops)
    print(json.dumps(result))
    sys.exit(0 if result["verdict"] == "continue" else 1)


if __name__ == "__main__":
    main()
