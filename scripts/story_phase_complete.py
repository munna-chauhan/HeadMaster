#!/bin/sh
""":"
for c in python3 py3 python py; do command -v "$c" >/dev/null 2>&1 && exec "$c" "$0" "$@"; done
for d in /c/Python* /c/Python*/Python* "/c/Program Files/Python"* "/c/Program Files/Python"*/Python* "/c/Program Files (x86)/Python"* "/c/Program Files (x86)/Python"*/Python* "$HOME/AppData/Local/Programs/Python/Python"* "$LOCALAPPDATA/Programs/Python/Python"*; do
  for n in python.exe python3.exe; do
    [ -x "$d/$n" ] && exec "$d/$n" "$0" "$@"
  done
done
echo "[HeadMaster] No python interpreter found (tried python3, py3, python, py, and common Windows install dirs)" >&2
exit 127
":"""
"""Single-call story completion — replaces per-phase gate_transition + run_logger calls.

Before: 4x gate_transition + 4x run_logger = 8 subprocess calls per story.
After:  story_phase_complete start + complete = 2 subprocess calls per story.

Usage:
  sh scripts/story_phase_complete.py <project> <slug> <story-key> start
  sh scripts/story_phase_complete.py <project> <slug> <story-key> checkpoint --phase A
  sh scripts/story_phase_complete.py <project> <slug> <story-key> complete [--phases A,C,D]
  sh scripts/story_phase_complete.py <project> <slug> <story-key> fail <reason>
  sh scripts/story_phase_complete.py <project> <slug> <story-key> defer <reason>
  sh scripts/story_phase_complete.py <project> <slug> <story-key> blocked <reason>
  sh scripts/story_phase_complete.py <project> <slug> <story-key> review
  sh scripts/story_phase_complete.py <project> <slug> <story-key> qa

checkpoint: appends phase to phases_completed without changing status. Safe to call mid-story
  after each phase commit so resume can detect partial progress after a session crash.

Story status is written to loop_state.json only. JIRA_BREAKDOWN*.md files are read-only content.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import file_lock

REPO_ROOT = Path(__file__).resolve().parent.parent


def _update_loop_state(state_file: Path, story_key: str, phases: list, status: str) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    fh = open(state_file, "a+", encoding="utf-8")
    file_lock.acquire(fh)
    try:
        fh.seek(0)
        content = fh.read()
        state = json.loads(content) if content.strip() else {}
        stories = state.setdefault("stories", {})
        story = stories.setdefault(story_key, {"phases_completed": []})
        completed = story.setdefault("phases_completed", [])
        for p in phases:
            if p not in completed:
                completed.append(p)
        completed.sort()
        story["status"] = status
        story["updated"] = datetime.now(timezone.utc).isoformat()
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(state, indent=2))
        fh.flush()
    finally:
        file_lock.release(fh)
        fh.close()


def _checkpoint_loop_state(state_file: Path, story_key: str, phase: str) -> None:
    """Append phase to phases_completed without changing status. Idempotent."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    fh = open(state_file, "a+", encoding="utf-8")
    file_lock.acquire(fh)
    try:
        fh.seek(0)
        content = fh.read()
        state = json.loads(content) if content.strip() else {}
        stories = state.setdefault("stories", {})
        story = stories.setdefault(story_key, {"phases_completed": [], "status": "IN_PROGRESS"})
        completed = story.setdefault("phases_completed", [])
        if phase not in completed:
            completed.append(phase)
        completed.sort()
        story["updated"] = datetime.now(timezone.utc).isoformat()
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(state, indent=2))
        fh.flush()
    finally:
        file_lock.release(fh)
        fh.close()


def _log(project: str, slug: str, story_key: str, action: str, detail: str = "") -> None:
    log_path = REPO_ROOT / "memory" / "features" / project / slug / "run-log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] [{story_key}] [{action}]{(' ' + detail) if detail else ''}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def main() -> None:
    if len(sys.argv) < 5:
        print("Usage: story_phase_complete.py <project> <slug> <story-key> <action> [args]",
              file=sys.stderr)
        sys.exit(1)

    project, slug, story_key, action = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    state_file = REPO_ROOT / "memory" / "features" / project / slug / "loop_state.json"

    if action == "start":
        _update_loop_state(state_file, story_key, [], "IN_PROGRESS")
        _log(project, slug, story_key, "STORY_START")
        print(f"[story] {story_key}: started", file=sys.stderr)

    elif action == "checkpoint":
        phase = ""
        if "--phase" in sys.argv:
            idx = sys.argv.index("--phase")
            phase = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if not phase:
            print("checkpoint requires --phase <code>", file=sys.stderr)
            sys.exit(1)
        _checkpoint_loop_state(state_file, story_key, phase.strip().upper())
        _log(project, slug, story_key, "PHASE_CHECKPOINT", f"phase={phase.strip().upper()}")
        print(f"[story] {story_key}: checkpoint phase={phase.strip().upper()}", file=sys.stderr)

    elif action == "complete":
        phases_str = ""
        if "--phases" in sys.argv:
            idx = sys.argv.index("--phases")
            phases_str = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        phases = [p.strip() for p in phases_str.split(",") if p.strip()] if phases_str else ["A", "B"]
        _update_loop_state(state_file, story_key, phases, "COMPLETE")
        _log(project, slug, story_key, "STORY_COMPLETE", f"phases={','.join(phases)}")
        print(f"[story] {story_key}: complete ({','.join(phases)})", file=sys.stderr)

    elif action == "fail":
        reason = sys.argv[5][:200] if len(sys.argv) > 5 else "unspecified"
        _update_loop_state(state_file, story_key, [], "FAILED")
        _log(project, slug, story_key, "STORY_FAIL", reason)
        print(f"[story] {story_key}: failed — {reason}", file=sys.stderr)

    elif action == "defer":
        reason = sys.argv[5][:200] if len(sys.argv) > 5 else "unspecified"
        _update_loop_state(state_file, story_key, [], "DEFERRED")
        _log(project, slug, story_key, "STORY_DEFER", reason)
        print(f"[story] {story_key}: deferred — {reason}", file=sys.stderr)

    elif action == "blocked":
        reason = sys.argv[5][:200] if len(sys.argv) > 5 else "unspecified"
        _update_loop_state(state_file, story_key, [], "BLOCKED")
        _log(project, slug, story_key, "STORY_BLOCKED", reason)
        print(f"[story] {story_key}: blocked — {reason}", file=sys.stderr)

    elif action == "review":
        _update_loop_state(state_file, story_key, [], "IN_REVIEW")
        _log(project, slug, story_key, "STORY_REVIEW")
        print(f"[story] {story_key}: in review", file=sys.stderr)

    elif action == "qa":
        _update_loop_state(state_file, story_key, [], "IN_QA")
        _log(project, slug, story_key, "STORY_QA")
        print(f"[story] {story_key}: in qa", file=sys.stderr)

    else:
        print(f"Unknown action: {action}. Valid: start | checkpoint | complete | fail | defer | blocked | review | qa",
              file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
