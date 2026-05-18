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
"""
autonomy_config.py

Two orthogonal axes:
1. autonomous flag  — phase transitions + ambiguity handling
2. plan/design gates — discussion depth (independent of axis 1)
"""

from config_utils import ConfigResolver

_config = ConfigResolver()


# ── Axis 1: autonomous mode ─────────────────────────────

def is_autonomous() -> bool:
    """
    True = pipeline flows automatically between phases.
           Ambiguity handled by assumption + log.
    False = human initiates each phase.
            Ambiguity handled by ask-user.md + wait.
    """
    return _config.get('autonomous', default=False)


def handle_ambiguity() -> str:
    """
    Returns 'ask' or 'assume' based on autonomous mode.
    Use this wherever the pipeline encounters ambiguity.
    """
    return 'assume' if is_autonomous() else 'ask'


def phase_transition() -> str:
    """
    Returns 'auto' or 'wait' based on autonomous mode.
    'wait' = pipeline stops, human must initiate next phase.
    'auto' = pipeline continues immediately.
    """
    return 'auto' if is_autonomous() else 'wait'


# ── Axis 2: discussion gates ────────────────────────────
# Independent of autonomous mode

def gate_enabled(phase: str) -> bool:
    """
    Controls discussion depth within a phase.
    Independent of autonomous mode.

    True  = deep discussion via ask-user.md
    False = agent decides, documents reasoning

    PR gate is not configurable — always True.
    Execute gate is not configurable — behaviour-driven.
    """
    if phase == 'pr':
        return True   # always human, not configurable
    if phase in ('execute', 'breakdown'):
        return None   # not a gate — behaviour-driven
    # Handle nested gate structure
    return _config.get(f'gates.{phase}.interactive', default=True)


# ── Capabilities ────────────────────────────────────────

def jira_push_enabled() -> bool:
    """Read jira_push from active project config, not capabilities."""
    active = _config.get('projects.active', default='default')
    return _config.get(f'projects.{active}.jira_push', default=False)


def get_epic_strategy() -> str:
    return _config.get('capabilities.epic_strategy',
                       default='auto_create')


def get_jira_retry_enabled() -> bool:
    return _config.get('capabilities.jira_retry', default=True)


def get_gap_classifier_enabled() -> bool:
    return _config.get('capabilities.gap_classifier', default=False)


def get_test_classifier_enabled() -> bool:
    return _config.get('capabilities.test_classifier', default=False)


# ── Pipeline self-edit prohibition ──────────────────────

def pipeline_self_edit_allowed() -> bool:
    """
    Never allowed in autonomous mode.
    In supervised mode: human gate I10 fires.
    """
    return not is_autonomous()


# ── Review mode (nested under gates) ────────────────────

def get_review_mode(phase: str) -> str:
    """
    Get review mode for phase (plan/design).
    Returns: 'skip' | 'auto' | 'human_in_loop'
    Default: 'human_in_loop'
    """
    return _config.get(f'gates.{phase}.review.mode', default='human_in_loop')


if __name__ == "__main__":
    import sys

    _USAGE = (
        "Usage: autonomy_config.py <command> [args]\n"
        "Commands:\n"
        "  is-autonomous            → true|false\n"
        "  handle-ambiguity         → ask|assume\n"
        "  phase-transition         → wait|auto\n"
        "  gate-enabled <phase>     → true|false|none\n"
        "  get-epic-strategy        → auto_create|link_existing|none\n"
        "  get-review-mode <phase>  → skip|auto|human_in_loop\n"
        "  jira-push-enabled        → true|false\n"
    )

    if len(sys.argv) < 2:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "is-autonomous":
        print("true" if is_autonomous() else "false")
    elif cmd == "handle-ambiguity":
        print(handle_ambiguity())
    elif cmd == "phase-transition":
        print(phase_transition())
    elif cmd == "gate-enabled":
        if len(sys.argv) < 3:
            print("gate-enabled requires <phase>", file=sys.stderr)
            sys.exit(1)
        result = gate_enabled(sys.argv[2])
        print("none" if result is None else ("true" if result else "false"))
    elif cmd == "get-epic-strategy":
        print(get_epic_strategy())
    elif cmd == "get-review-mode":
        if len(sys.argv) < 3:
            print("get-review-mode requires <phase>", file=sys.stderr)
            sys.exit(1)
        print(get_review_mode(sys.argv[2]))
    elif cmd == "jira-push-enabled":
        print("true" if jira_push_enabled() else "false")
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
