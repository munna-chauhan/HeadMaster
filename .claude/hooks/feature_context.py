#!/usr/bin/env python3
"""
SessionStart hook: inject active feature context.
Scans memory/features/ for in-progress work, outputs additionalContext
so Claude starts oriented without re-reading artifact files.
Zero tokens wasted on orientation. Fast model reads this, not Opus.
"""
import json
import os
import sys


def find_active_features(project_dir):
    """Find features with in-progress planning or design work."""
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
            with open(loop_state_path, "r") as f:
                state = json.load(f)
        except Exception:
            continue

        planning = state.get("planning", {})
        design = state.get("design", {})

        # Check planning in-progress
        planning_status = planning.get("status", "")
        design_status = design.get("status", "")

        # Check PRD gate string
        prd_path = os.path.join(project_dir, "docs", "features", slug_dir, "planning", "PRD.md")
        prd_approved = False
        prd_exists = os.path.exists(prd_path)
        if prd_exists:
            try:
                with open(prd_path, "r", encoding="utf-8") as f:
                    prd_approved = "PRD Status: APPROVED" in f.read()
            except Exception:
                pass

        # Check TDD review verdict
        tdd_review_path = os.path.join(project_dir, "docs", "features", slug_dir, "design", "TDD_REVIEW.md")
        tdd_approved = False
        if os.path.exists(tdd_review_path):
            try:
                with open(tdd_review_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    tdd_approved = "APPROVED" in content or "CONDITIONAL" in content
            except Exception:
                pass

        # Determine current stage
        stage = None
        blocker = None

        if not prd_exists:
            # Check which planning file exists
            feature_draft = os.path.join(project_dir, "docs", "features", slug_dir, "planning", "FEATURE_DRAFT.md")
            discovery_notes = os.path.join(project_dir, "docs", "features", slug_dir, "planning", "DISCOVERY_NOTES.md")
            if os.path.exists(discovery_notes):
                try:
                    with open(discovery_notes, "r", encoding="utf-8") as f:
                        if "All Questions Resolved: YES" in f.read():
                            stage = "planning/Draft"
                        else:
                            stage = "planning/Discover"
                except Exception:
                    stage = "planning/Discover"
            elif os.path.exists(feature_draft):
                stage = "planning/Discover"
            else:
                stage = "planning/Init"
        elif prd_exists and not prd_approved:
            blocker = planning.get("last_blocker_type")
            if blocker:
                stage = f"planning/Review — loop-back ({blocker})"
            else:
                stage = "planning/Review"
        elif prd_approved and not tdd_approved:
            # Check design state
            sdn_path = os.path.join(project_dir, "docs", "features", slug_dir, "design", "SYSTEM_DESIGN_NOTES.md")
            if not os.path.exists(sdn_path):
                stage = "design/Architect"
            else:
                try:
                    with open(sdn_path, "r", encoding="utf-8") as f:
                        if "Architecture Locked: YES" in f.read():
                            stage = "design/Engineer" if not os.path.exists(tdd_review_path) else "design/Review"
                        else:
                            stage = "design/Architect"
                except Exception:
                    stage = "design/Architect"
            design_blocker = design.get("last_blocker_type")
            if design_blocker and design_status != "PASS":
                stage = f"{stage} — loop-back ({design_blocker})"
        elif prd_approved and tdd_approved:
            # Check breakdown/execute state
            breakdown_path = os.path.join(project_dir, "docs", "features", slug_dir, "breakdown", "JIRA_BREAKDOWN.md")
            if os.path.exists(breakdown_path):
                try:
                    with open(breakdown_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "IN PROGRESS" in content or "SCANNING" in content or "IN REVIEW" in content or "IN QA" in content:
                        stage = "execute/in-progress"
                    elif "COMPLETE" in content:
                        stage = "execute/complete — ready for /breakdown merge-gate"
                    else:
                        stage = "execute/ready — run /execute {slug}".format(slug=slug_dir)
                except Exception:
                    stage = "breakdown/ready — run /execute {slug}".format(slug=slug_dir)
            else:
                stage = "breakdown/ready — run /breakdown {slug}".format(slug=slug_dir)

        if stage and "COMPLETE" not in stage:
            active.append({
                "slug": slug_dir,
                "stage": stage,
                "planning_iteration": planning.get("iteration", 0),
                "design_iteration": design.get("iteration", 0),
            })

    return active


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    project_dir = hook_input.get("cwd", os.getcwd())

    active = find_active_features(project_dir)

    if not active:
        sys.exit(0)

    lines = ["## Active Feature Work\n"]
    for f in active:
        lines.append(f"- **{f['slug']}** — stage: `{f['stage']}`")
        if f["planning_iteration"] > 1:
            lines.append(f"  planning loops: {f['planning_iteration']}")
        if f["design_iteration"] > 1:
            lines.append(f"  design loops: {f['design_iteration']}")

    lines.append("\nResume with `/plan <slug>` or `/design <slug>`. State auto-detected.")

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
