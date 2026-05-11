#!/usr/bin/env python
"""
FIX-019: Pre-spawn prompt validation hook
Validates Agent tool calls to prevent implementation context leaking to review subagents.

Fires on: PreToolUse event for Agent tool
Returns: {"ok": true} to allow, {"ok": false, "reason": "..."} to block

Contract: Review subagents (review-agent, qa-engineer) must receive ONLY:
- Story acceptance criteria
- TDD design sections
- Git diff output

Blocked content:
- Implementation file paths (src/**/*.{java,ts,go,py} excluding tests)
- Code blocks from implementation
- Phase A execution traces
- References to developer.md agent output
"""

import json
import re
import sys
from pathlib import Path

# Review subagents that must never receive implementation context
REVIEW_SUBAGENTS = {"review-agent", "qa-engineer", "tdd-reviewer", "prd-reviewer"}

# Default implementation path prefixes (overridden by config.yml security.impl_path_prefixes)
_DEFAULT_PREFIXES = ["src", "lib", "app", "internal"]


def _load_impl_prefixes() -> list[str]:
    """Read impl path prefixes from config.yml, fall back to defaults."""
    try:
        hook_dir = Path(__file__).resolve().parent
        config_path = hook_dir.parents[1] / "config.yml"
        if not config_path.exists():
            return _DEFAULT_PREFIXES
        import yaml  # type: ignore
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        prefixes = cfg.get("security", {}).get("impl_path_prefixes", None)
        return prefixes if isinstance(prefixes, list) and prefixes else _DEFAULT_PREFIXES
    except Exception:
        return _DEFAULT_PREFIXES


def validate_spawn_prompt(tool_call: dict) -> tuple[bool, str]:
    """Validate Agent tool call prompt for isolation violations."""
    if tool_call.get("name") != "Agent":
        return True, ""

    params = tool_call.get("parameters", {})
    subagent_type = params.get("subagent_type", "")
    prompt = params.get("prompt", "")

    if subagent_type not in REVIEW_SUBAGENTS:
        return True, ""

    prompt_without_diff = re.sub(r'(Git Diff:|git diff|^\+\+\+.*$|^---.*$)', '', prompt, flags=re.MULTILINE)

    # CRITICAL: implementation file references in prose
    prefixes = _load_impl_prefixes()
    prefix_pattern = "|".join(re.escape(p) for p in prefixes)
    impl_file_pattern = (
        rf'(?:Review|Check|Read|See|in|at)\s+'
        rf'((?:{prefix_pattern})/[^\s]+\.(?:java|ts|tsx|go|py|js|jsx|rb|rs|c|cpp|h))\b'
    )
    matches = re.findall(impl_file_pattern, prompt_without_diff, re.IGNORECASE)
    if matches:
        non_test = [m for m in matches if not re.search(r'\.(test|spec)\.', m) and '_test\.' not in m]
        if non_test:
            return False, f"[CRITICAL] Implementation file reference in prose: {non_test[0]}"

    # CRITICAL: large code blocks (threshold lowered to 100 chars)
    code_block_pattern = r'```[a-z]*\n(.{50,}?)```'
    code_blocks = re.findall(code_block_pattern, prompt, re.DOTALL)
    if code_blocks and any(len(b) > 100 for b in code_blocks):
        return False, "[CRITICAL] Large code block in prompt (>100 chars) — likely implementation context"

    # MEDIUM: Phase A keyword references
    phase_a_keywords = [
        "Phase A",
        "implement/SKILL.md",
        "developer.md output",
        "implementation complete",
        "code was written",
    ]
    for keyword in phase_a_keywords:
        if keyword.lower() in prompt.lower():
            return False, f"[MEDIUM] Phase A reference in prompt: '{keyword}'"

    if "developer agent" in prompt.lower() or "implementer" in prompt.lower():
        return False, "[MEDIUM] Reference to developer/implementer agent in prompt"

    return True, ""


def main():
    """Hook entry point."""
    try:
        # Read payload from stdin
        payload = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}

        # Claude Code PreToolUse payload: tool_name + tool_input (not tool_call)
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})

        if not tool_input or tool_name != "Agent":
            # Not an Agent call or empty payload — allow
            print(json.dumps({"ok": True}))
            sys.exit(0)

        # Reconstruct into validate_spawn_prompt's expected shape
        tool_call = {"name": tool_name, "parameters": tool_input}

        # Validate
        is_valid, reason = validate_spawn_prompt(tool_call)

        if is_valid:
            print(json.dumps({"ok": True}))
        else:
            print(json.dumps({
                "ok": False,
                "reason": f"Subagent isolation violation: {reason}"
            }))

    except Exception as e:
        # Fail-closed on error
        print(json.dumps({
            "ok": False,
            "reason": f"Pre-spawn validation error: {str(e)}"
        }))
        sys.exit(0)


if __name__ == "__main__":
    main()
