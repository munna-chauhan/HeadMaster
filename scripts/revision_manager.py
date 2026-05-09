#!/usr/bin/env python
"""Revision lifecycle manager for pipeline re-openings.

Usage:
    python scripts/revision_manager.py reopen <project> <slug> <stage> [message]
    python scripts/revision_manager.py check  <project> <slug> <stage>
    python scripts/revision_manager.py close  <project> <slug> <rev_id>

Commands:
    reopen  Reopen a stage: transitions loop_state.json, writes REVISION_NOTES.md
    check   Returns JSON: whether a revision is open for this stage/cascade
    close   Marks open revision as resolved (OPEN → CLOSED in log)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import file_lock

REPO_ROOT = Path(__file__).resolve().parents[1]

VALID_STAGES = ["planning", "design", "breakdown", "execute"]
VALID_SCOPES = ["minor", "standard", "structural"]

# Scope-gated cascade: minor=no downstream, standard=immediate downstream, structural=full
CASCADE_MAP: dict[str, dict[str, list[str]]] = {
    "planning": {
        "minor":      [],
        "standard":   ["design"],
        "structural": ["design", "breakdown", "execute"],
    },
    "design": {
        "minor":      [],
        "standard":   ["breakdown", "execute"],
        "structural": ["breakdown", "execute"],
    },
    "breakdown": {
        "minor":      [],
        "standard":   ["execute"],
        "structural": ["execute"],
    },
    "execute": {
        "minor":      [],
        "standard":   [],
        "structural": [],
    },
}

# Artifact keys transitioned to "revision" when a stage is reopened
ARTIFACT_STAGE_MAP: dict[str, list[str]] = {
    "planning":  ["planning/PRD.md"],
    "design":    [
        "design/SYSTEM_DESIGN_NOTES.md",
        "design/TDD_MASTER.md",
        "design/TDD_REVIEW.md",
    ],
    "breakdown": [],   # populated dynamically from loop_state artifacts
    "execute":   [],
}


def _load_state(state_file: Path) -> dict:
    if not state_file.exists():
        return {}
    content = state_file.read_text(encoding="utf-8").strip()
    return json.loads(content) if content else {}


def _save_state(state_file: Path, state: dict) -> None:
    fh = open(state_file, "r+", encoding="utf-8")
    file_lock.acquire(fh)
    try:
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(state, indent=2))
        fh.flush()
    finally:
        file_lock.release(fh)
        fh.close()


def _next_rev_id(log_path: Path) -> str:
    if not log_path.exists():
        return "REV-001"
    ids = re.findall(r"## (REV-\d+)", log_path.read_text(encoding="utf-8"))
    if not ids:
        return "REV-001"
    return f"REV-{max(int(r.split('-')[1]) for r in ids) + 1:03d}"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_reopen(project: str, slug: str, stage: str, scope: str = "standard", message: str = "") -> None:
    if stage not in VALID_STAGES:
        print(json.dumps({"error": f"Invalid stage '{stage}'. Valid: {VALID_STAGES}"}))
        sys.exit(1)
    if scope not in VALID_SCOPES:
        print(json.dumps({"error": f"Invalid scope '{scope}'. Valid: {VALID_SCOPES}"}))
        sys.exit(1)

    memory_dir = REPO_ROOT / "memory" / "features" / project / slug
    state_file = memory_dir / "loop_state.json"
    if not state_file.exists():
        print(json.dumps({"error": f"loop_state.json not found: {state_file}"}))
        sys.exit(1)

    state = _load_state(state_file)
    cascade = CASCADE_MAP[stage][scope]
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    # Build affected artifact key list
    affected_keys = list(ARTIFACT_STAGE_MAP.get(stage, []))
    if stage == "breakdown":
        for k in state.get("artifacts", {}):
            if k.startswith("breakdown/JIRA_BREAKDOWN"):
                affected_keys.append(k)

    # Include TDD_{NAME}.md keys for design stage
    if stage == "design":
        for k in state.get("artifacts", {}):
            if k.startswith("design/TDD_") and k not in affected_keys:
                affected_keys.append(k)

    # Transition artifact statuses → revision
    for key in affected_keys:
        if key in state.get("artifacts", {}):
            state["artifacts"][key]["status"] = "revision"

    # Determine next rev_id
    log_path = REPO_ROOT / "docs" / "features" / project / slug / "REVISION_NOTES.md"
    rev_id = _next_rev_id(log_path)

    # Update pipeline block
    state.setdefault("pipeline", {})
    state["pipeline"].update({
        "phase":             stage,
        "stage":             "revision",
        "revision_open":     True,
        "revision_id":       rev_id,
        "revision_stage":    stage,
        "revision_cascade":  cascade,
        "revision_opened":   now.isoformat(),
    })
    state["last_updated"] = now.isoformat()

    _save_state(state_file, state)

    # Write REVISION_NOTES.md — scaffold phase sections for reopened stage + cascade
    log_path.parent.mkdir(parents=True, exist_ok=True)
    active_phases = [stage] + cascade
    phase_hints = {
        "planning":  "<!-- what changed in PRD.md and why -->",
        "design":    "<!-- TDD sections affected, architectural decisions -->",
        "breakdown": "<!-- add: <story title> | suspend: <KEY> | reopen: <KEY> -->",
        "execute":   "<!-- reopen: <KEY,KEY> | notes -->",
    }
    entry_lines = [
        f"\n## {rev_id} [{today}] {stage} OPEN",
        f"**Reason:** {message or '(none)'}",
        "",
    ]
    for phase in active_phases:
        entry_lines.append(f"### {phase.title()}")
        entry_lines.append(phase_hints.get(phase, "<!-- fill -->"))
        entry_lines.append("")
    entry_lines.append("---")
    entry = "\n".join(entry_lines) + "\n"

    if log_path.exists():
        log_path.write_text(log_path.read_text(encoding="utf-8") + entry, encoding="utf-8")
    else:
        log_path.write_text(f"# Revision Notes — {slug}\n" + entry, encoding="utf-8")

    next_cmd = f"/breakdown {slug}" if stage in ("planning", "design") else f"/execute {slug}"
    print(json.dumps({
        "rev_id":             rev_id,
        "stage":              stage,
        "scope":              scope,
        "cascade":            cascade,
        "artifacts_affected": affected_keys,
        "log":                str(log_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "next":               next_cmd,
        "error":              None,
    }, indent=2))


def cmd_check(project: str, slug: str, stage: str) -> None:
    """Return JSON indicating whether an open revision applies to this stage."""
    state_file = REPO_ROOT / "memory" / "features" / project / slug / "loop_state.json"
    if not state_file.exists():
        print(json.dumps({"revision_open": False, "error": None}))
        return

    pipeline = _load_state(state_file).get("pipeline", {})
    if not pipeline.get("revision_open"):
        print(json.dumps({"revision_open": False, "error": None}))
        return

    rev_stage = pipeline.get("revision_stage", "")
    cascade   = pipeline.get("revision_cascade", [])
    applies   = stage == rev_stage or stage in cascade

    print(json.dumps({
        "revision_open":    applies,
        "rev_id":           pipeline.get("revision_id"),
        "revision_stage":   rev_stage,
        "revision_cascade": cascade,
        "log":              f"docs/features/{project}/{slug}/REVISION_NOTES.md",
        "error":            None,
    }))


def cmd_close(project: str, slug: str, rev_id: str) -> None:
    """Mark an open revision as closed."""
    state_file = REPO_ROOT / "memory" / "features" / project / slug / "loop_state.json"
    if not state_file.exists():
        print(json.dumps({"error": "loop_state.json not found"}))
        sys.exit(1)

    state    = _load_state(state_file)
    pipeline = state.get("pipeline", {})

    if not pipeline.get("revision_open"):
        print(json.dumps({"closed": False, "message": "No open revision", "error": None}))
        return

    active_id = pipeline.get("revision_id")
    if active_id != rev_id:
        print(json.dumps({"error": f"Active revision is {active_id}, not {rev_id}"}))
        sys.exit(1)

    # Remove revision flags
    for key in ("revision_open", "revision_id", "revision_stage", "revision_cascade", "revision_opened"):
        pipeline.pop(key, None)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state_file, state)

    # REVISION_NOTES.md: mark entry CLOSED
    today    = datetime.now(timezone.utc).date().isoformat()
    log_path = REPO_ROOT / "docs" / "features" / project / slug / "REVISION_NOTES.md"
    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        # Replace first "[...] OPEN" belonging to this rev_id
        content = re.sub(
            rf"(## {re.escape(rev_id)} \[.*?\]) OPEN",
            rf"\1 CLOSED [{today}]",
            content,
            count=1,
        )
        log_path.write_text(content, encoding="utf-8")

    print(json.dumps({"closed": True, "rev_id": rev_id, "error": None}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "reopen":
        if len(sys.argv) < 5:
            print("Usage: revision_manager.py reopen <project> <slug> <stage> [--scope minor|standard|structural] [message]")
            sys.exit(1)
        project, slug, stage = sys.argv[2], sys.argv[3], sys.argv[4]
        scope = "standard"
        remaining = sys.argv[5:]
        if "--scope" in remaining:
            idx = remaining.index("--scope")
            if idx + 1 < len(remaining):
                scope = remaining[idx + 1]
                remaining = remaining[:idx] + remaining[idx + 2:]
        message = " ".join(remaining)
        cmd_reopen(project, slug, stage, scope, message)

    elif cmd == "check":
        if len(sys.argv) < 5:
            print("Usage: revision_manager.py check <project> <slug> <stage>")
            sys.exit(1)
        cmd_check(sys.argv[2], sys.argv[3], sys.argv[4])

    elif cmd == "close":
        if len(sys.argv) < 5:
            print("Usage: revision_manager.py close <project> <slug> <rev_id>")
            sys.exit(1)
        cmd_close(sys.argv[2], sys.argv[3], sys.argv[4])

    else:
        print(f"Unknown command: {cmd}. Valid: reopen | check | close")
        sys.exit(1)


if __name__ == "__main__":
    main()
