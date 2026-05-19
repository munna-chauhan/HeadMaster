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
"""Atomic pipeline state transition. Called by skills when a gate passes.

Usage:
    sh scripts/gate_transition.py <project> <slug> <phase> <stage>
    sh scripts/gate_transition.py <project> <slug> rollback
    sh scripts/gate_transition.py <project> <slug> artifact <rel-path> <status>
    sh scripts/gate_transition.py <project> <slug> execute phase-complete --story <key> --phase <code>

Examples:
    sh scripts/gate_transition.py acme my-feature planning APPROVED
    sh scripts/gate_transition.py acme my-feature design Engineer
    sh scripts/gate_transition.py acme my-feature artifact "planning/PRD.md" APPROVED
    sh scripts/gate_transition.py acme my-feature artifact "design/TDD_search-service.md" approved
    sh scripts/gate_transition.py acme my-feature artifact "breakdown/JIRA_BREAKDOWN_search-service.md" pushed
    sh scripts/gate_transition.py acme my-feature released-section "search-service" "breakdown/JIRA_BREAKDOWN_search-service.md" 5 13
    sh scripts/gate_transition.py acme my-feature rollback
"""
import json
import sys
import platform
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import file_lock

REPO_ROOT = Path(__file__).resolve().parents[1]


def record_gate_passed(project: str, slug: str, phase: str, stage: str) -> None:
    """Record a gate transition for performance tracking purposes.

    Called after a successful gate transition. Failures here must not block
    the transition itself.
    """
    # Intentionally a no-op. Kept as a stable call site for gate transitions.
    pass


def main() -> None:
    """Execute pipeline gate transition with atomic state updates.

    Note: Uses file locking (Sprint 5 #34) to prevent race conditions during
    read-modify-write. Issue #51 duplicate — confirmed resolved.
    """
    if len(sys.argv) < 4:
        print("gate_transition: requires <project> <slug> <command> [args]", file=sys.stderr)
        sys.exit(1)

    project = sys.argv[1]
    slug = sys.argv[2]

    # Handle artifact status update: gate_transition.py {project} {slug} artifact {path} {status}
    if sys.argv[3] == "artifact":
        if len(sys.argv) < 6:
            print("Usage: gate_transition.py <project> <slug> artifact <rel-path> <status>", file=sys.stderr)
            sys.exit(1)

        rel_path = sys.argv[4]
        status   = sys.argv[5]

        memory_dir = REPO_ROOT / "memory" / "features" / project / slug
        memory_dir.mkdir(parents=True, exist_ok=True)
        state_file = memory_dir / "loop_state.json"

        lock_file = open(state_file, 'a+', encoding="utf-8")
        file_lock.acquire(lock_file)
        try:
            lock_file.seek(0)
            content = lock_file.read()
            state = json.loads(content) if content else {}
            if "artifacts" not in state:
                state["artifacts"] = {}
            state["artifacts"][rel_path] = {"status": status}
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps(state, indent=2))
            lock_file.flush()
        finally:
            file_lock.release(lock_file)
            lock_file.close()

        print(f"[gate] {slug}: artifact {rel_path} → {status}", file=sys.stderr)
        sys.exit(0)

    # Handle rollback command
    if len(sys.argv) == 4 and sys.argv[3] == "rollback":
        memory_dir = REPO_ROOT / "memory" / "features" / project / slug
        state_file = memory_dir / "loop_state.json"
        backup_file = memory_dir / "loop_state.json.bak"

        if not backup_file.exists():
            print(f"[gate] No backup found for {slug}", file=sys.stderr)
            sys.exit(1)

        # Restore backup
        backup_file.replace(state_file)
        print(f"[gate] {slug}: restored from backup", file=sys.stderr)
        sys.exit(0)

    # Handle phase-complete command for per-story phase tracking (FIX-001)
    if len(sys.argv) >= 5 and sys.argv[4] == "phase-complete":
        if "--story" not in sys.argv or "--phase" not in sys.argv:
            print("Usage: gate_transition.py <project> <slug> execute phase-complete --story <key> --phase <code>", file=sys.stderr)
            sys.exit(1)

        story_idx = sys.argv.index("--story")
        phase_idx = sys.argv.index("--phase")

        if story_idx + 1 >= len(sys.argv) or phase_idx + 1 >= len(sys.argv):
            print("Error: --story and --phase require values", file=sys.stderr)
            sys.exit(1)

        story_key = sys.argv[story_idx + 1]
        phase_code = sys.argv[phase_idx + 1]

        if phase_code not in ["A", "B", "C", "D", "E"]:
            print(f"Error: Invalid phase code '{phase_code}'. Valid: A, B, C, D, E", file=sys.stderr)
            sys.exit(1)

        memory_dir = REPO_ROOT / "memory" / "features" / project / slug
        memory_dir.mkdir(parents=True, exist_ok=True)
        state_file = memory_dir / "loop_state.json"

        # Read existing state with lock
        lock_file = open(state_file, 'a+', encoding="utf-8")
        file_lock.acquire(lock_file)

        try:
            lock_file.seek(0)
            content = lock_file.read()

            if content:
                try:
                    state = json.loads(content)
                except json.JSONDecodeError:
                    state = {"pipeline": {}, "stories": {}}
            else:
                state = {"pipeline": {}, "stories": {}}

            # Initialize stories dict if missing
            if "stories" not in state:
                state["stories"] = {}

            # Initialize story entry if missing
            if story_key not in state["stories"]:
                state["stories"][story_key] = {"phases_completed": []}

            # Add phase to phases_completed if not already present
            story_data = state["stories"][story_key]
            if "phases_completed" not in story_data:
                story_data["phases_completed"] = []

            if phase_code not in story_data["phases_completed"]:
                story_data["phases_completed"].append(phase_code)
                # Sort to maintain A, B, C, D, E order
                story_data["phases_completed"].sort()

            # Write with lock held
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps(state, indent=2))
            lock_file.flush()

            print(f"[gate] {story_key}: Phase {phase_code} complete. Completed phases: {story_data['phases_completed']}", file=sys.stderr)
        finally:
            file_lock.release(lock_file)
            lock_file.close()

        sys.exit(0)

    # Handle released-section: gate_transition.py {project} {slug} released-section {name} {breakdown-file} {n-stories} {total-sp}
    if sys.argv[3] == "released-section":
        if len(sys.argv) < 8:
            print("Usage: gate_transition.py <project> <slug> released-section <tdd-name> <breakdown-file> <n-stories> <total-sp>", file=sys.stderr)
            sys.exit(1)

        tdd_name       = sys.argv[4]
        breakdown_file = sys.argv[5]
        n_stories      = sys.argv[6]
        total_sp       = sys.argv[7]

        memory_dir = REPO_ROOT / "memory" / "features" / project / slug
        memory_dir.mkdir(parents=True, exist_ok=True)
        state_file = memory_dir / "loop_state.json"

        lock_file = open(state_file, 'a+', encoding="utf-8")
        file_lock.acquire(lock_file)
        try:
            lock_file.seek(0)
            content = lock_file.read()
            state = json.loads(content) if content.strip() else {}
            state.setdefault("released_sections", {})[tdd_name] = {
                "breakdown_file": breakdown_file,
                "released_date": datetime.now(timezone.utc).date().isoformat(),
                "stories": int(n_stories),
                "sp": int(total_sp),
            }
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps(state, indent=2))
            lock_file.flush()
        finally:
            file_lock.release(lock_file)
            lock_file.close()

        print(f"[gate] {slug}: released-section {tdd_name} → {breakdown_file}", file=sys.stderr)
        sys.exit(0)

    # Handle plan-stage: gate_transition.py {project} {slug} plan-stage {stage} {status}
    if sys.argv[3] == "plan-stage":
        if len(sys.argv) < 6:
            print("Usage: gate_transition.py <project> <slug> plan-stage <stage> <status>", file=sys.stderr)
            sys.exit(1)
        stage_name  = sys.argv[4]
        stage_status = sys.argv[5]
        memory_dir = REPO_ROOT / "memory" / "features" / project / slug
        memory_dir.mkdir(parents=True, exist_ok=True)
        state_file = memory_dir / "loop_state.json"
        lock_file = open(state_file, 'a+', encoding="utf-8")
        file_lock.acquire(lock_file)
        try:
            lock_file.seek(0)
            content = lock_file.read()
            state = json.loads(content) if content.strip() else {}
            state.setdefault("planning_stages", {})[stage_name] = stage_status
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps(state, indent=2))
            lock_file.flush()
        finally:
            file_lock.release(lock_file)
            lock_file.close()
        print(f"[gate] {slug}: planning_stages.{stage_name} → {stage_status}", file=sys.stderr)
        sys.exit(0)

    # Handle design-stage: gate_transition.py {project} {slug} design-stage {stage} {status}
    if sys.argv[3] == "design-stage":
        if len(sys.argv) < 6:
            print("Usage: gate_transition.py <project> <slug> design-stage <stage> <status>", file=sys.stderr)
            sys.exit(1)
        stage_name  = sys.argv[4]
        stage_status = sys.argv[5]
        memory_dir = REPO_ROOT / "memory" / "features" / project / slug
        memory_dir.mkdir(parents=True, exist_ok=True)
        state_file = memory_dir / "loop_state.json"
        lock_file = open(state_file, 'a+', encoding="utf-8")
        file_lock.acquire(lock_file)
        try:
            lock_file.seek(0)
            content = lock_file.read()
            state = json.loads(content) if content.strip() else {}
            state.setdefault("design_stages", {})[stage_name] = stage_status
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps(state, indent=2))
            lock_file.flush()
        finally:
            file_lock.release(lock_file)
            lock_file.close()
        print(f"[gate] {slug}: design_stages.{stage_name} → {stage_status}", file=sys.stderr)
        sys.exit(0)

    # Handle route reclassification: gate_transition.py {project} {slug} reclassify --route {route} ...
    if sys.argv[3] == "reclassify":
        args = sys.argv[4:]
        route = args[args.index("--route") + 1] if "--route" in args else None
        from_route = args[args.index("--from") + 1] if "--from" in args else None
        checkpoint = args[args.index("--checkpoint") + 1] if "--checkpoint" in args else "manual"
        evidence_raw = args[args.index("--evidence") + 1] if "--evidence" in args else ""
        evidence = [e.strip() for e in evidence_raw.split(";") if e.strip()]

        if not route:
            print("Error: --route required for reclassify", file=sys.stderr)
            sys.exit(1)

        memory_dir = REPO_ROOT / "memory" / "features" / project / slug
        memory_dir.mkdir(parents=True, exist_ok=True)
        state_file = memory_dir / "loop_state.json"

        lock_file = open(state_file, 'a+', encoding="utf-8")
        file_lock.acquire(lock_file)
        try:
            lock_file.seek(0)
            content = lock_file.read()
            state = json.loads(content) if content.strip() else {}
            prev_route = from_route or state.get("route", "unknown")
            state["route"] = route
            state.setdefault("route_history", []).append({
                "from":       prev_route,
                "to":         route,
                "checkpoint": checkpoint,
                "evidence":   evidence,
                "timestamp":  datetime.now(timezone.utc).isoformat(),
            })
            state["last_updated"] = datetime.now(timezone.utc).isoformat()
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps(state, indent=2))
            lock_file.flush()
        finally:
            file_lock.release(lock_file)
            lock_file.close()

        print(f"[gate] {slug}: route reclassified {prev_route} → {route} ({checkpoint})", file=sys.stderr)
        sys.exit(0)

    if len(sys.argv) < 5:
        print("Usage: gate_transition.py <project> <slug> <phase> <stage> [--artifact <path>] | <project> <slug> rollback", file=sys.stderr)
        sys.exit(1)

    phase = sys.argv[3]
    stage = sys.argv[4]

    artifact = None
    if "--artifact" in sys.argv:
        idx = sys.argv.index("--artifact")
        if idx + 1 < len(sys.argv):
            artifact = sys.argv[idx + 1]

    memory_dir = REPO_ROOT / "memory" / "features" / project / slug
    memory_dir.mkdir(parents=True, exist_ok=True)
    state_file = memory_dir / "loop_state.json"

    # Read existing state with lock
    lock_file = open(state_file, 'a+', encoding="utf-8")
    file_lock.acquire(lock_file)

    try:
        lock_file.seek(0)
        content = lock_file.read()

        if content:
            try:
                state = json.loads(content)
            except json.JSONDecodeError:
                state = {}
        else:
            state = {}

        # Backup current state before updating
        if content:
            backup_file = state_file.with_suffix(".json.bak")
            backup_file.write_text(content, encoding="utf-8")

        # Block phase advance while a revision is open
        if state.get("pipeline", {}).get("revision_open"):
            rev_id = state["pipeline"].get("revision_id", "unknown")
            print(f"[gate] BLOCKED: revision {rev_id} is open — close it before advancing phase", file=sys.stderr)
            sys.exit(1)

        # Update pipeline key atomically
        state["pipeline"] = {
            "phase": phase,
            "stage": stage,
            "gate_passed": datetime.now(timezone.utc).isoformat(),
        }
        if artifact:
            state["pipeline"]["artifact"] = artifact

        # Write with lock held
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(json.dumps(state, indent=2))
        lock_file.flush()
    finally:
        file_lock.release(lock_file)
        lock_file.close()

    print(f"[gate] {slug}: {phase}/{stage}", file=sys.stderr)

    # Performance tracking — failures must not block the transition
    try:
        record_gate_passed(project, slug, phase, stage)
    except Exception:
        pass


if __name__ == "__main__":
    main()
