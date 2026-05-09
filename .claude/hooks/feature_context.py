#!/usr/bin/env python
"""
SessionStart hook: inject active feature context.

Detects current pipeline phase from artifacts, finds the most recent
handoff file tagged to that phase, injects only its content.

Phase filtering prevents planning handoffs bleeding into design sessions
and design handoffs bleeding into execute sessions.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from state_manager import detect_phase
from config_utils import ConfigResolver


# Phase hierarchy — used to filter handoffs by relevance
# A handoff is relevant if its phase == current phase
# Handoffs from earlier phases are stale and not injected
PHASE_ORDER = ["planning", "design", "breakdown", "execute"]


def find_relevant_handoff(slug_memory_path: str, current_phase: str) -> str | None:
    """
    Find the most recent handoff file tagged to current_phase.
    Reads the Phase: line from each session-*.md file.
    Returns file content of the best match, or None.
    """
    memory_path = Path(slug_memory_path)
    candidates = sorted(
        memory_path.glob("session-*.md"),
        key=lambda p: p.name,
        reverse=True  # most recent first
    )

    for handoff_file in candidates:
        try:
            content = handoff_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract Phase: tag from first 5 lines
        phase_tag = None
        for line in content.splitlines()[:5]:
            m = re.match(r"Phase:\s*(\w+)", line, re.IGNORECASE)
            if m:
                phase_tag = m.group(1).lower()
                break

        if phase_tag == current_phase:
            return content

    return None


def read_active_project(project_dir: str) -> str:
    """Extract active project from config.yml via ConfigResolver."""
    try:
        resolver = ConfigResolver(Path(project_dir) / "config.yml")
        return resolver.active_project
    except Exception:
        return "default"


def find_active_features(project_dir: str) -> list[dict]:
    active = []
    project = read_active_project(project_dir)
    memory_base = os.path.join(project_dir, "memory", "features", project)
    if not os.path.exists(memory_base):
        return active

    for slug_dir in os.listdir(memory_base):
        slug_path = os.path.join(memory_base, slug_dir)
        if not os.path.isdir(slug_path):
            continue

        loop_state_path = os.path.join(slug_path, "loop_state.json")
        if not os.path.exists(loop_state_path):
            continue

        try:
            state = json.loads(Path(loop_state_path).read_text(encoding="utf-8"))
        except Exception:
            continue

        # Use shared phase detector
        try:
            phase, stage, _hint = detect_phase(project, slug_dir, project_dir)
        except Exception:
            continue

        # Skip completed features
        if stage == "complete":
            continue

        gates_passed = state.get("gates_passed", {})
        planning_iteration = sum(1 for k in gates_passed if k.startswith("planning/"))
        design_iteration = sum(1 for k in gates_passed if k.startswith("design/"))
        blocker_history = state.get("blocker_history", [])
        last_blocker = blocker_history[-1] if blocker_history else None

        # Find phase-matched handoff — only inject if active within 4h
        handoff_content = find_relevant_handoff(slug_path, phase)
        if handoff_content:
            snapshot_path = os.path.join(slug_path, "auto-snapshot.json")
            if os.path.exists(snapshot_path):
                try:
                    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
                    saved_str = snap.get("auto_saved", "")
                    if saved_str:
                        saved = datetime.fromisoformat(saved_str)
                        if saved.tzinfo is None:
                            saved = saved.replace(tzinfo=timezone.utc)
                        if (datetime.now(timezone.utc) - saved).total_seconds() > 14400:
                            handoff_content = None
                except Exception:
                    pass

        active.append({
            "slug":               slug_dir,
            "phase":              phase,
            "stage":              stage,
            "planning_iteration": planning_iteration,
            "design_iteration":   design_iteration,
            "last_blocker":       last_blocker,
            "handoff":            handoff_content,
        })

    return active


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception as e:
        try:
            from datetime import datetime as _dt
            _log = REPO_ROOT / ".remember" / "logs" / "hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} feature_context.py: {type(e).__name__}: {e}\n")
        except Exception:
            pass
        sys.exit(0)

    project_dir = hook_input.get("cwd", os.getcwd())
    active = find_active_features(project_dir)

    if not active:
        sys.exit(0)

    # Compact output — only primary feature gets handoff to save tokens
    MAX_HANDOFF_LINES = 30
    lines = []

    primary = active[0]
    lines.append(f"**{primary['slug']}** — `{primary['phase']}/{primary['stage']}`")

    # Only inject handoff for primary feature, capped at 30 lines
    if primary["handoff"]:
        handoff_lines = primary["handoff"].splitlines()[:MAX_HANDOFF_LINES]
        lines.append(f"\n### Handoff ({primary['phase']}):")
        lines.extend(handoff_lines)
        if len(primary["handoff"].splitlines()) > MAX_HANDOFF_LINES:
            lines.append(f"  ... truncated ({len(primary['handoff'].splitlines()) - MAX_HANDOFF_LINES} more lines)")

    # Other features: one-liner only, no handoff
    if len(active) > 1:
        for f in active[1:5]:  # Cap at 4 more
            lines.append(f"- {f['slug']}: `{f['phase']}/{f['stage']}`")
        if len(active) > 5:
            lines.append(f"  +{len(active) - 5} more")

    lines.append(f"\nNext: `/{primary['phase']} {primary['slug']}`")

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines)
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
