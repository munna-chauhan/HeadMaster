#!/usr/bin/env python3
"""UserPromptSubmit hook — tracks active skill in a flag file."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

FLAG_FILE = Path.home() / ".claude" / ".HeadMaster-active"
KNOWN_SKILLS = {"plan", "design", "breakdown", "execute", "navigate", "draw", "compress",
                "implement", "security-scan", "review-code", "qa-integration", "review-system", "jira-ops"}


def parse_prompt(prompt: str) -> tuple[str, str] | None:
    """Extract (skill, slug) if prompt starts with a known slash command."""
    parts = prompt.strip().split()
    if not parts or not parts[0].startswith("/"):
        return None
    skill = parts[0][1:]  # strip leading /
    if skill not in KNOWN_SKILLS:
        return None
    slug = parts[1] if len(parts) > 1 else "unknown"
    return skill, slug


def atomic_write(path: Path, data: dict) -> None:
    """Write JSON atomically: write to .tmp then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data), encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def read_model_from_env() -> str:
    """Read model from CLAUDE_MODEL env var (set by Claude Code runtime)."""
    return os.environ.get("CLAUDE_MODEL", os.environ.get("ANTHROPIC_MODEL", ""))


def main() -> None:
    if len(sys.argv) < 2:
        return
    prompt = sys.argv[1]
    result = parse_prompt(prompt)
    if result is None:
        return
    skill, slug = result
    # Preserve existing model if already set; update with current env if available
    model = read_model_from_env()
    existing = {}
    if FLAG_FILE.exists():
        try:
            existing = json.loads(FLAG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            pass
    atomic_write(FLAG_FILE, {
        "skill": skill,
        "slug": slug,
        "model": model or existing.get("model", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    main()
