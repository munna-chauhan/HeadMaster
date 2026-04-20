#!/usr/bin/env python3
"""
PreToolUse hook — intercepts Bash tool calls containing git commands.
Blocks destructive git operations that don't match expected branch patterns.

Returns JSON to stdout:
  {"decision": "block", "reason": "..."} — prevents execution
  {} — allows execution (pass-through)
"""

import json
import os
import re
import sys

# Branch name patterns considered valid for HeadMaster operations
VALID_BRANCH_PATTERNS = [
    r"^story/[a-z0-9\-]+$",
    r"^feature/[a-z0-9\-]+$",
    r"^epic/[a-z0-9\-]+$",
    r"^child-epic/[a-z0-9\-]+$",
    r"^fix/[a-z0-9\-]+$",
    r"^main$",
    r"^master$",
]

# Git subcommands that are always safe (read-only or local-only)
SAFE_SUBCOMMANDS = {
    "status", "log", "diff", "show", "branch", "checkout", "fetch",
    "stash", "add", "commit", "merge", "tag", "remote",
    "rev-parse", "show-ref", "ls-files", "ls-remote", "config",
    "shortlog", "describe", "name-rev", "cherry", "pull",
}

# Commands that are ALWAYS blocked regardless of context
ALWAYS_BLOCKED = [
    r"git\s+push\s+.*--force",
    r"git\s+push\s+.*-f\b",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-fd",
    r"git\s+clean\s+-f\b",
    r"git\s+rebase",
    r"git\s+cherry-pick",
    r"git\s+filter-branch",
    r"git\s+reflog\s+expire",
]


def extract_git_command(tool_input: str) -> str | None:
    """Extract the git command from a bash tool input string."""
    # Match 'git <subcommand> ...' anywhere in the command string
    match = re.search(r"\bgit\s+(.+)", tool_input)
    return match.group(0).strip() if match else None


def extract_git_subcommand(git_cmd: str) -> str | None:
    """Extract the subcommand (e.g., 'push', 'branch') from a git command."""
    match = re.match(r"git\s+(\S+)", git_cmd)
    return match.group(1) if match else None


def is_valid_branch_name(name: str) -> bool:
    """Check if a branch name matches HeadMaster's naming conventions."""
    name = name.strip().strip("'\"")
    return any(re.match(p, name) for p in VALID_BRANCH_PATTERNS)


def check_always_blocked(cmd: str) -> str | None:
    """Return reason if command matches an always-blocked pattern."""
    for pattern in ALWAYS_BLOCKED:
        if re.search(pattern, cmd, re.IGNORECASE):
            return f"Blocked: '{cmd}' matches destructive pattern. Requires explicit human approval."
    return None


def validate_push(cmd: str) -> str | None:
    """Validate git push commands — check target branch is valid."""
    # git push origin <branch>
    match = re.search(r"git\s+push\s+(\S+)\s+(?:--delete\s+)?(\S+)", cmd)
    if not match:
        # bare 'git push' or 'git push origin' — allow (pushes current branch)
        return None

    remote = match.group(1)
    branch = match.group(2)

    # Strip flags that might appear before branch name
    if branch.startswith("-"):
        return None  # flag, not a branch — let git handle it

    if not is_valid_branch_name(branch):
        return (
            f"Blocked: git push target '{branch}' does not match expected branch patterns "
            f"(story/*, feature/*, epic/*, fix/*, main, master). "
            f"Verify branch name and retry."
        )
    return None


def validate_delete(cmd: str) -> str | None:
    """Validate git push --delete and git branch -D/-d commands."""
    # git push origin --delete <branch>
    delete_match = re.search(r"git\s+push\s+\S+\s+--delete\s+(\S+)", cmd)
    if delete_match:
        branch = delete_match.group(1)
        if not is_valid_branch_name(branch):
            return f"Blocked: remote delete target '{branch}' is not a recognized branch pattern."
        # Block deletion of protected branches
        if branch in ("main", "master") or branch.startswith("release/"):
            return f"Blocked: cannot delete protected branch '{branch}'."
        return None

    # git branch -D <branch> or git branch -d <branch>
    local_delete = re.search(r"git\s+branch\s+-[dD]\s+(\S+)", cmd)
    if local_delete:
        branch = local_delete.group(1)
        if branch in ("main", "master") or branch.startswith("release/"):
            return f"Blocked: cannot delete protected branch '{branch}'."
        if not is_valid_branch_name(branch):
            return f"Blocked: local delete target '{branch}' is not a recognized branch pattern."
    return None


def validate_git_command(cmd: str) -> str | None:
    """
    Validate a git command. Returns None if safe, or a reason string if blocked.
    """
    # Check always-blocked patterns first
    reason = check_always_blocked(cmd)
    if reason:
        return reason

    subcommand = extract_git_subcommand(cmd)
    if not subcommand:
        return None  # Not a parseable git command — let it through

    # Read-only / local-only commands are always safe
    if subcommand in SAFE_SUBCOMMANDS:
        # But check for destructive flags on otherwise-safe commands
        if subcommand == "branch":
            return validate_delete(cmd)
        return None

    # Push requires branch validation
    if subcommand == "push":
        push_reason = validate_push(cmd)
        if push_reason:
            return push_reason
        return validate_delete(cmd)  # handles --delete flag

    # Unknown subcommand — block by default (fail-closed)
    return f"Blocked: 'git {subcommand}' not in allowed list. Requires explicit human approval."


def main() -> None:
    """
    Read tool input from stdin (Claude Code hook protocol).
    Emit JSON decision to stdout.
    """
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, Exception):
        # Can't parse input — pass through (don't block on hook failure)
        print(json.dumps({}))
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    git_cmd = extract_git_command(command)
    if not git_cmd:
        # Not a git command — pass through
        print(json.dumps({}))
        sys.exit(0)

    reason = validate_git_command(git_cmd)
    if reason:
        print(json.dumps({
            "decision": "block",
            "reason": reason,
        }))
    else:
        print(json.dumps({}))

    sys.exit(0)


if __name__ == "__main__":
    main()
