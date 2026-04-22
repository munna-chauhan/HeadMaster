#!/usr/bin/env python3
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
from pathlib import Path


# Phase hierarchy — used to filter handoffs by relevance
# A handoff is relevant if its phase == current phase
# Handoffs from earlier phases are stale and not injected
PHASE_ORDER = ["planning", "design", "breakdown", "execute"]


def detect_stage(project_dir: str, slug: str) -> tuple[str, str]:
    """
    Returns (phase, stage) for the feature.
    PRIMARY: reads pipeline state from loop_state.json.
    FALLBACK: infers from artifacts if loop_state.json lacks pipeline key.
    """
    memory_path = os.path.join(project_dir, "memory", "features", slug, "loop_state.json")

    # PRIMARY: structured state from loop_state.json
    if os.path.exists(memory_path):
        try:
            state = json.loads(Path(memory_path).read_text(encoding="utf-8"))
            pipeline = state.get("pipeline")
            if pipeline and "phase" in pipeline and "stage" in pipeline:
                return pipeline["phase"], pipeline["stage"]
        except Exception:
            pass

    # FALLBACK: infer from artifacts (legacy behavior for features without pipeline key)
    return _detect_stage_from_artifacts(project_dir, slug)


def _detect_stage_from_artifacts(project_dir: str, slug: str) -> tuple[str, str]:
    """Legacy artifact-based detection. Used as fallback when loop_state.json lacks pipeline key."""
    base = os.path.join(project_dir, "docs", "features", slug)
    planning  = os.path.join(base, "planning")
    design    = os.path.join(base, "design")
    breakdown = os.path.join(base, "breakdown")

    prd_path = os.path.join(planning, "PRD.md")
    prd_exists = os.path.exists(prd_path)
    prd_approved = False
    if prd_exists:
        try:
            with open(prd_path, "rb") as f:
                f.seek(max(0, os.path.getsize(prd_path) - 200))
                tail = f.read().decode("utf-8", errors="ignore")
            prd_approved = "PRD Status: APPROVED" in tail
        except Exception:
            pass

    tdd_review_path = os.path.join(design, "TDD_REVIEW.md")
    tdd_approved = False
    if os.path.exists(tdd_review_path):
        try:
            with open(tdd_review_path, "rb") as f:
                head = f.read(500).decode("utf-8", errors="ignore")
            tdd_approved = "APPROVED" in head or "CONDITIONAL" in head
        except Exception:
            pass

    # Execute phase
    if prd_approved and tdd_approved:
        bd_file = os.path.join(breakdown, "JIRA_BREAKDOWN.md")
        if os.path.exists(bd_file):
            try:
                with open(bd_file, "rb") as f:
                    head = f.read(2048).decode("utf-8", errors="ignore")
                if any(m in head for m in ["🔄 IN PROGRESS", "🔍 SCANNING", "👁️ IN REVIEW", "🧪 IN QA"]):
                    return "execute", "in-progress"
                if "✅ COMPLETE" in head and "⏳ NEW" not in head:
                    return "execute", "complete"
            except Exception:
                pass
            return "execute", "ready"
        return "breakdown", "ready"

    # Design phase
    if prd_approved and not tdd_approved:
        sdn_path = os.path.join(design, "SYSTEM_DESIGN_NOTES.md")
        if not os.path.exists(sdn_path):
            return "design", "Architect"
        try:
            with open(sdn_path, "rb") as f:
                f.seek(max(0, os.path.getsize(sdn_path) - 200))
                tail = f.read().decode("utf-8", errors="ignore")
            locked = "Architecture Locked: YES" in tail
        except Exception:
            locked = False
        if locked:
            return "design", "Review" if os.path.exists(tdd_review_path) else "Engineer"
        return "design", "Architect"

    # Planning phase
    if prd_exists and not prd_approved:
        return "planning", "Review"

    discovery = os.path.join(planning, "DISCOVERY_NOTES.md")
    if os.path.exists(discovery):
        try:
            with open(discovery, "rb") as f:
                f.seek(max(0, os.path.getsize(discovery) - 100))
                tail = f.read().decode("utf-8", errors="ignore")
            resolved = "All Questions Resolved: YES" in tail
        except Exception:
            resolved = False
        return "planning", "Draft" if resolved else "Discover"

    if os.path.exists(os.path.join(planning, "FEATURE_DRAFT.md")):
        return "planning", "Discover"

    return "planning", "Init"


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


def find_active_features(project_dir: str) -> list[dict]:
    active = []
    memory_base = os.path.join(project_dir, "memory", "features")
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

        phase, stage = detect_stage(project_dir, slug_dir)

        # Skip completed features
        if stage == "complete":
            continue

        planning = state.get("planning", {})
        design   = state.get("design", {})

        # Find phase-matched handoff
        handoff_content = find_relevant_handoff(slug_path, phase)

        active.append({
            "slug":               slug_dir,
            "phase":              phase,
            "stage":              stage,
            "planning_iteration": planning.get("iteration", 0),
            "design_iteration":   design.get("iteration", 0),
            "last_blocker":       planning.get("last_blocker_type") or design.get("last_blocker_type"),
            "handoff":            handoff_content,
        })

    return active


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception as e:
        try:
            from pathlib import Path as _P
            from datetime import datetime as _dt
            _log = _P.home() / "memory" / "hook-errors.log"
            with open(_log, "a") as _f:
                _f.write(f"{_dt.now().isoformat()} feature_context.py: {type(e).__name__}: {e}\n")
        except Exception:
            pass
        sys.exit(0)

    project_dir = hook_input.get("cwd", os.getcwd())
    active = find_active_features(project_dir)

    if not active:
        sys.exit(0)

    lines = ["## Active Feature Work\n"]

    for f in active:
        lines.append(f"- **{f['slug']}** — phase: `{f['phase']}` | stage: `{f['stage']}`")

        if f["planning_iteration"] > 1:
            lines.append(f"  planning loops: {f['planning_iteration']}")
        if f["design_iteration"] > 1:
            lines.append(f"  design loops: {f['design_iteration']}")
        if f["last_blocker"]:
            lines.append(f"  last blocker: {f['last_blocker']}")

        # Inject phase-matched handoff — trimmed to 60 lines to cap token cost
        if f["handoff"]:
            handoff_lines = f["handoff"].splitlines()[:60]
            lines.append(f"\n### Last {f['phase']} handoff: {f['slug']}")
            lines.extend(handoff_lines)
            lines.append("")

    lines.append(f"Resume: `/navigate {active[0]['slug']}` or `/{active[0]['phase'].split('/')[0]} {active[0]['slug']}`")

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
