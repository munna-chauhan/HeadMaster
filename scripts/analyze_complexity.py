#!/usr/bin/env python
"""Analyze project complexity by comparing with main branch.

Usage:
    python scripts/analyze_complexity.py [-b base_branch] [-v]

Default base_branch: main
"""

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_git(cmd: list[str]) -> str:
    """Run git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def get_current_branch() -> str:
    """Get current branch name."""
    return run_git(["branch", "--show-current"]) or "HEAD"


def get_diff_stats(base: str) -> dict:
    """Get detailed diff statistics."""
    stats = {
        "files_changed": 0,
        "insertions": 0,
        "deletions": 0,
        "commits": 0,
        "file_details": [],
    }

    # File count, insertions, deletions
    shortstat = run_git(["diff", base, "--shortstat"])
    if shortstat:
        parts = shortstat.split(",")
        for part in parts:
            if "file" in part:
                stats["files_changed"] = int(part.split()[0])
            elif "insertion" in part:
                stats["insertions"] = int(part.split()[0])
            elif "deletion" in part:
                stats["deletions"] = int(part.split()[0])

    # Commit count
    commit_count = run_git(["rev-list", "--count", f"{base}..HEAD"])
    if commit_count:
        stats["commits"] = int(commit_count)

    # Per-file details (top 10 by total change)
    numstat = run_git(["diff", base, "--numstat"])
    if numstat:
        file_changes = []
        for line in numstat.split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                add = int(parts[0]) if parts[0] != "-" else 0
                delete = int(parts[1]) if parts[1] != "-" else 0
                filepath = " ".join(parts[2:])
                total = add + delete
                file_changes.append((filepath, add, delete, total))

        # Sort by total change, take top 10
        file_changes.sort(key=lambda x: x[3], reverse=True)
        stats["file_details"] = file_changes[:10]

    return stats


def categorize_changes(file_details: list) -> dict:
    """Categorize changes by type."""
    categories = defaultdict(int)

    for filepath, add, delete, _ in file_details:
        path = Path(filepath)
        if path.match("tests/**/*") or path.match("**/test_*.py"):
            categories["tests"] += add + delete
        elif path.match("docs/**/*") or path.suffix == ".md":
            categories["docs"] += add + delete
        elif "security" in str(path).lower():
            categories["security"] += add + delete
        elif path.match("scripts/**/*"):
            categories["scripts"] += add + delete
        elif path.match(".claude/**/*"):
            categories["claude"] += add + delete
        else:
            categories["implementation"] += add + delete

    return dict(categories)


def complexity_tier(net_loc: int) -> tuple[str, str, str]:
    """Determine complexity tier."""
    if net_loc < 500:
        return "🟢", "SMALL", "Single-phase execution, quick review"
    elif net_loc < 2000:
        return "🟡", "MEDIUM", "Standard execution, 1-2 review rounds"
    elif net_loc < 5000:
        return "🟠", "LARGE", "Multi-day, careful review, may need breakup"
    else:
        return "🔴", "X-LARGE", "Epic-level, definitely needs breakdown"


def format_number(n: int) -> str:
    """Format number with thousands separator."""
    return f"{n:,}"


def main():
    # Set UTF-8 encoding for Windows console
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description="Analyze feature complexity by comparing with base branch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument("-b", "--base", default="main", help="Base branch to compare against (default: main)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Single-line output: TIER: +N/-N LOC, N files, N commits. Full report written to file.")
    parser.add_argument("-o", "--output", help="Write full report to file instead of stdout")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    base = args.base
    current = get_current_branch()

    stats = get_diff_stats(base)

    if stats["files_changed"] == 0:
        print("No changes detected.")
        sys.exit(0)

    net_change = stats["insertions"] - stats["deletions"]
    emoji, tier_name, tier_desc = complexity_tier(abs(net_change))
    categories = categorize_changes(stats["file_details"])

    # Quiet mode: single-line verdict for agent consumption
    if args.quiet:
        risks = []
        if categories.get("tests", 0) == 0 and stats["files_changed"] > 0:
            risks.append("no-tests")
        if categories.get("security", 0) > 0:
            risks.append("security-changes")
        risk_str = f" risks=[{','.join(risks)}]" if risks else ""
        print(f"{tier_name}: +{stats['insertions']}/-{stats['deletions']} LOC, {stats['files_changed']} files, {stats['commits']} commits{risk_str}")
        sys.exit(0)

    # Full report — build as lines, write to file or stdout
    lines = []
    lines.append("Feature Complexity Report")
    lines.append("=" * 60)
    lines.append(f"Branch: {current}")
    lines.append(f"Base: {base}")
    lines.append("")
    lines.append(f"Files Changed:     {stats['files_changed']}")
    lines.append(f"Insertions:        +{format_number(stats['insertions'])}")
    lines.append(f"Deletions:         -{format_number(stats['deletions'])}")
    lines.append(f"Net Change:        {'+' if net_change >= 0 else ''}{format_number(net_change)} LOC")
    lines.append(f"Commits:           {stats['commits']}")
    lines.append("")
    lines.append(f"Complexity Tier:   {emoji} {tier_name}")
    lines.append(f"                   {tier_desc}")
    lines.append("")

    if stats["file_details"]:
        lines.append("Top Changed Files:")
        for filepath, add, delete, _ in stats["file_details"][:5]:
            if delete == 0:
                change_str = f"+{add} LOC"
            elif add == 0:
                change_str = f"-{delete} LOC"
            else:
                change_str = f"+{add} -{delete} LOC"
            lines.append(f"  {filepath:<50} {change_str}")
        lines.append("")

    if categories:
        lines.append("Risk Indicators:")
        if categories.get("tests", 0) > 0:
            lines.append(f"  ✓ Test coverage added ({format_number(categories['tests'])} LOC in tests/)")
        else:
            lines.append("  ⚠ No test changes detected")
        if categories.get("docs", 0) > 0:
            lines.append(f"  ✓ Documentation updated ({format_number(categories['docs'])} LOC in docs/)")
        if categories.get("security", 0) > 0:
            lines.append(f"  ⚠ Security-sensitive changes ({format_number(categories['security'])} LOC)")
        lines.append("")

    lines.append("Recommendation:")
    if tier_name == "SMALL":
        lines.append("  - Execute as single unit, standard review")
    elif tier_name == "MEDIUM":
        lines.append("  - Standard /execute workflow, 1-2 review rounds")
    elif tier_name == "LARGE":
        lines.append("  - Break into smaller stories, multi-day execution")
    else:
        lines.append("  - Epic-level — use /breakdown to split into stories")

    report = "\n".join(lines)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"{tier_name}: +{stats['insertions']}/-{stats['deletions']} LOC. Report: {out_path}")
    else:
        print(report)

    sys.exit(0)


if __name__ == "__main__":
    main()
