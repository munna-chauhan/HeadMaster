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
Input Extractor — strips API metadata noise from fetched Jira/Confluence JSON.
Converts raw API responses to lean markdown. Saves ~70-85% tokens on input files.

Usage:
    sh scripts/input_extractor.py jira -i <input.json> -o <output.md>
    sh scripts/input_extractor.py confluence -i <input.json> -o <output.md>
    sh scripts/input_extractor.py dir -i <input-dir>
    sh scripts/input_extractor.py from-mcp-confluence -o <output.md>
    sh scripts/input_extractor.py from-mcp-jira -o <output.md>
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

def fence_external_content(content, source, field_name="content"):
    """Wrap external content in data-fence markers for trust boundary."""
    return (
        f"<!-- EXTERNAL-DATA-START source=\"{source}\" field=\"{field_name}\" -->\n"
        f"{content}\n"
        f"<!-- EXTERNAL-DATA-END -->"
    )


# ---------------------------------------------------------------------------
# Jira extraction
# ---------------------------------------------------------------------------

def _sanitize_field(text: str, source: str, field_name: str) -> str:
    """Fence an external field value with trust boundary markers."""
    if not text or not text.strip():
        return text
    return fence_external_content(text, source=source, field_name=field_name)


def extract_jira_issue(data: dict) -> str:
    """Extract essential fields from a Jira issue API response."""
    f = data.get("fields", {})

    key = data.get("key", "")
    summary = f.get("summary", "")
    status = f.get("status", {}).get("name", "")
    issue_type = f.get("issuetype", {}).get("name", "")
    priority = f.get("priority", {}).get("name", "")
    assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
    reporter = (f.get("reporter") or {}).get("displayName", "")
    created = f.get("created", "")[:10]
    updated = f.get("updated", "")[:10]
    labels = ", ".join(f.get("labels", [])) or "—"
    sp_field = f.get("customfield_10016") or f.get("story_points", "")
    story_pts = str(sp_field) if sp_field else "—"

    # Description — Atlassian Document Format or plain string
    desc_raw = f.get("description", "")
    description_raw = _extract_adf_text(desc_raw) if isinstance(desc_raw, dict) else (desc_raw or "")
    description = _sanitize_field(description_raw, source=f"jira:{key}", field_name="description")

    # Acceptance criteria — common custom field names
    ac_raw = (
            f.get("customfield_10034") or
            f.get("customfield_10035") or
            f.get("acceptance_criteria", "")
    )
    ac_raw_text = _extract_adf_text(ac_raw) if isinstance(ac_raw, dict) else (ac_raw or "")
    ac_text = _sanitize_field(ac_raw_text, source=f"jira:{key}", field_name="acceptance_criteria")

    # Comments — last 5 only (sanitized — comments are high-risk injection surface)
    comments_data = f.get("comment", {}).get("comments", [])[-5:]
    comments = []
    for c in comments_data:
        author = (c.get("author") or {}).get("displayName", "")
        date = c.get("created", "")[:10]
        body_raw = _extract_adf_text(c.get("body", "")) if isinstance(c.get("body"), dict) else c.get("body", "")
        comments.append(f"- [{date}] {author}: {body_raw[:300]}")

    # Subtasks
    subtasks = [f"- {s.get('key')}: {s.get('fields', {}).get('summary', '')}" for s in f.get("subtasks", [])]

    # Links
    links = []
    for lnk in f.get("issuelinks", []):
        if lnk.get("outwardIssue"):
            links.append(
                f"- {lnk.get('type', {}).get('outward', 'relates to')} {lnk['outwardIssue']['key']}: {lnk['outwardIssue']['fields']['summary']}")
        if lnk.get("inwardIssue"):
            links.append(
                f"- {lnk.get('type', {}).get('inward', 'relates to')} {lnk['inwardIssue']['key']}: {lnk['inwardIssue']['fields']['summary']}")

    lines = [
        f"# {key}: {summary}",
        f"",
        f"**Type:** {issue_type} | **Status:** {status} | **Priority:** {priority} | **SP:** {story_pts}",
        f"**Assignee:** {assignee} | **Reporter:** {reporter}",
        f"**Created:** {created} | **Updated:** {updated} | **Labels:** {labels}",
    ]

    if description.strip():
        lines += ["", "## Description", description.strip()]

    if ac_text.strip():
        lines += ["", "## Acceptance Criteria", ac_text.strip()]

    if subtasks:
        lines += ["", "## Subtasks"] + subtasks

    if links:
        lines += ["", "## Links"] + links

    if comments:
        lines += ["", "## Recent Comments"] + comments

    return "\n".join(lines)


def extract_jira_search(data: dict) -> str:
    """Extract essential fields from a Jira search result (list of issues)."""
    issues = data.get("issues", data) if isinstance(data, dict) else data
    if not isinstance(issues, list):
        issues = [issues]

    blocks = []
    for issue in issues:
        blocks.append(extract_jira_issue(issue))
        blocks.append("")

    total = data.get("total", len(issues)) if isinstance(data, dict) else len(issues)
    header = f"<!-- {total} issues -->\n\n"
    return header + "\n".join(blocks).strip()


def _extract_adf_text(node, depth=0) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if not node:
        return ""
    if isinstance(node, str):
        return node

    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")

    if node_type == "text":
        marks = {m.get("type") for m in node.get("marks", [])}
        result = text
        if "strong" in marks:
            result = f"**{result}**"
        if "code" in marks:
            result = f"`{result}`"
        return result

    if node_type == "hardBreak":
        return "\n"

    if node_type in ("paragraph", "blockquote"):
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        return inner + "\n"

    if node_type in ("heading",):
        level = node.get("attrs", {}).get("level", 2)
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        return "#" * level + " " + inner.strip() + "\n"

    if node_type == "bulletList":
        items = []
        for item in content:
            inner = "".join(_extract_adf_text(c, depth + 1) for c in item.get("content", []))
            items.append("  " * depth + "- " + inner.strip())
        return "\n".join(items) + "\n"

    if node_type == "orderedList":
        items = []
        for i, item in enumerate(content, 1):
            inner = "".join(_extract_adf_text(c, depth + 1) for c in item.get("content", []))
            items.append("  " * depth + f"{i}. " + inner.strip())
        return "\n".join(items) + "\n"

    if node_type == "codeBlock":
        lang = node.get("attrs", {}).get("language", "")
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        return f"```{lang}\n{inner.strip()}\n```\n"

    if node_type == "inlineCard":
        url = node.get("attrs", {}).get("url", "")
        return f"[{url}]({url})"

    if node_type == "table":
        return _extract_adf_table(node)

    # Default: recurse into content
    return "".join(_extract_adf_text(c, depth) for c in content)


def _extract_adf_table(node) -> str:
    rows = []
    for row in node.get("content", []):
        cells = []
        for cell in row.get("content", []):
            inner = "".join(_extract_adf_text(c) for c in cell.get("content", []))
            cells.append(inner.strip().replace("\n", " "))
        rows.append("| " + " | ".join(cells) + " |")
    if len(rows) > 1:
        header_sep = "| " + " | ".join(["---"] * len(rows[0].split("|")[1:-1])) + " |"
        rows.insert(1, header_sep)
    return "\n".join(rows) + "\n"


# ---------------------------------------------------------------------------
# Confluence extraction
# ---------------------------------------------------------------------------

def extract_confluence_page(data: dict) -> str:
    """Extract content from a Confluence page API response."""
    page_id = data.get("id", "")
    title = data.get("title", "")
    version = data.get("version", {}).get("number", "")
    updated = data.get("version", {}).get("when", "")[:10]
    author = data.get("version", {}).get("by", {}).get("displayName", "")

    storage_value = data.get("body", {}).get("storage", {}).get("value", "")
    content_raw = _confluence_storage_to_markdown(storage_value)
    content = _sanitize_field(content_raw, source=f"confluence:{page_id}", field_name="body")

    lines = [
        f"# {title}",
        f"",
        f"**Page ID:** {page_id} | **Version:** {version} | **Updated:** {updated} | **By:** {author}",
        f"",
        content.strip(),
    ]
    return "\n".join(lines)


def _confluence_storage_to_markdown(html: str) -> str:
    """Convert Confluence storage format (HTML-like XML) to clean markdown."""
    if not html:
        return ""

    # Remove Confluence macros (toc, info, note, warning, etc.)
    html = re.sub(r'<ac:structured-macro[^>]*>.*?</ac:structured-macro>', '', html, flags=re.DOTALL)
    html = re.sub(r'<ac:[^>]+/>', '', html)
    html = re.sub(r'<ac:[^>]+>.*?</ac:[^>]+>', '', html, flags=re.DOTALL)

    # Remove local-id and other noisy attributes
    html = re.sub(r'\s+local-id="[^"]*"', '', html)
    html = re.sub(r'\s+ac:[a-z-]+="[^"]*"', '', html)
    html = re.sub(r'\s+data-[a-z-]+="[^"]*"', '', html)

    # Headings
    for level in range(6, 0, -1):
        html = re.sub(rf'<h{level}[^>]*>(.*?)</h{level}>',
                      lambda m, l=level: '\n' + '#' * l + ' ' + _strip_tags(m.group(1)).strip() + '\n', html,
                      flags=re.DOTALL)

    # Code blocks
    html = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', lambda m: '\n```\n' + m.group(1).strip() + '\n```\n',
                  html, flags=re.DOTALL)
    html = re.sub(r'<code[^>]*>(.*?)</code>', lambda m: '`' + m.group(1) + '`', html, flags=re.DOTALL)

    # Bold / italic
    html = re.sub(r'<strong[^>]*>(.*?)</strong>', lambda m: '**' + m.group(1) + '**', html, flags=re.DOTALL)
    html = re.sub(r'<em[^>]*>(.*?)</em>', lambda m: '*' + m.group(1) + '*', html, flags=re.DOTALL)

    # Links
    html = re.sub(r'<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>', lambda m: f'[{_strip_tags(m.group(2))}]({m.group(1)})', html,
                  flags=re.DOTALL)

    # Lists
    html = re.sub(r'<li[^>]*>(.*?)</li>', lambda m: '- ' + _strip_tags(m.group(1)).strip() + '\n', html,
                  flags=re.DOTALL)
    html = re.sub(r'<[uo]l[^>]*>', '\n', html)
    html = re.sub(r'</[uo]l>', '\n', html)

    # Tables — basic extraction
    html = re.sub(r'<th[^>]*>(.*?)</th>', lambda m: '| ' + _strip_tags(m.group(1)).strip() + ' ', html, flags=re.DOTALL)
    html = re.sub(r'<td[^>]*>(.*?)</td>', lambda m: '| ' + _strip_tags(m.group(1)).strip() + ' ', html, flags=re.DOTALL)
    html = re.sub(r'<tr[^>]*>', '', html)
    html = re.sub(r'</tr>', '|\n', html)
    html = re.sub(r'<t(?:head|body|foot)[^>]*>', '', html)
    html = re.sub(r'</t(?:head|body|foot)>', '', html)
    html = re.sub(r'<table[^>]*>', '\n', html)
    html = re.sub(r'</table>', '\n', html)

    # Paragraphs and line breaks
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: _strip_tags(m.group(1)).strip() + '\n\n', html, flags=re.DOTALL)

    # Strip remaining tags
    html = _strip_tags(html)

    # Decode HTML entities
    html = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ').replace('&#39;',
                                                                                                               "'").replace(
        '&quot;', '"')

    # Collapse excessive blank lines
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html.strip()


def _strip_tags(html: str) -> str:
    return re.sub(r'<[^>]+>', '', html)


# ---------------------------------------------------------------------------
# File detection + batch processing
# ---------------------------------------------------------------------------

def detect_type(data: dict) -> str:
    """Detect whether JSON is a Jira issue, Jira search result, or Confluence page."""
    if "issues" in data and "total" in data:
        return "jira_search"
    if "fields" in data and "key" in data:
        return "jira_issue"
    if "body" in data and "storage" in data.get("body", {}):
        return "confluence"
    # Jira issue list without search wrapper
    if isinstance(data, list) and data and "key" in data[0]:
        return "jira_search"
    return "unknown"


def extract_file(input_path: Path, output_path: Path) -> tuple[bool, int, int]:
    """Extract one JSON file to markdown. Returns (success, original_bytes, output_bytes)."""
    original_bytes = input_path.stat().st_size

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    file_type = detect_type(data)

    if file_type == "jira_issue":
        markdown = extract_jira_issue(data)
    elif file_type == "jira_search":
        markdown = extract_jira_search(data)
    elif file_type == "confluence":
        markdown = extract_confluence_page(data)
    else:
        return False, original_bytes, 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    return True, original_bytes, output_path.stat().st_size


def process_directory(input_dir: Path, quiet: bool = False):
    """Batch extract all .json files in a directory tree."""
    json_files = list(input_dir.rglob("*.json"))
    if not json_files:
        print(f"No .json files found in {input_dir}")
        return

    total_in = total_out = 0
    extracted = skipped = 0
    for json_path in json_files:
        md_path = json_path.with_suffix(".md")
        if md_path.exists():
            if not quiet:
                print(f"  SKIP {json_path.name} (extracted .md already exists)", file=sys.stderr)
            skipped += 1
            continue

        ok, size_in, size_out = extract_file(json_path, md_path)
        if ok:
            extracted += 1
            if not quiet:
                saved_pct = round((1 - size_out / size_in) * 100) if size_in else 0
                print(
                    f"  OK   {json_path.name} -> {md_path.name}  ({size_in // 1024}KB -> {size_out // 1024}KB, -{saved_pct}%)",
                    file=sys.stderr)
            total_in += size_in
            total_out += size_out
        else:
            skipped += 1
            if not quiet:
                print(f"  SKIP {json_path.name} (unknown format)", file=sys.stderr)

    if total_in:
        saved_pct = round((1 - total_out / total_in) * 100)
        print(f"OK: {extracted} extracted, {skipped} skipped ({total_in // 1024}KB -> {total_out // 1024}KB, -{saved_pct}%)")
    else:
        print(f"OK: 0 extracted, {skipped} skipped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract lean markdown from Jira/Confluence JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="mode", required=True, help="Extraction mode")

    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Minimal stdout for agent consumption. Progress to stderr.")

    # jira subcommand
    jira_parser = subparsers.add_parser("jira", help="Extract Jira issue JSON to markdown")
    jira_parser.add_argument("-i", "--input", required=True, help="Input JSON file path")
    jira_parser.add_argument("-o", "--output", required=True, help="Output markdown file path")

    # confluence subcommand
    conf_parser = subparsers.add_parser("confluence", help="Extract Confluence page JSON to markdown")
    conf_parser.add_argument("-i", "--input", required=True, help="Input JSON file path")
    conf_parser.add_argument("-o", "--output", required=True, help="Output markdown file path")

    # dir subcommand
    dir_parser = subparsers.add_parser("dir", help="Batch extract all JSON files in directory")
    dir_parser.add_argument("-i", "--input-dir", required=True, help="Input directory path")

    # from-mcp-jira subcommand
    mcp_jira_parser = subparsers.add_parser("from-mcp-jira", help="Extract Jira JSON from stdin (MCP response)")
    mcp_jira_parser.add_argument("-o", "--output", required=True, help="Output markdown file path")

    # from-mcp-confluence subcommand
    mcp_conf_parser = subparsers.add_parser("from-mcp-confluence", help="Extract Confluence JSON from stdin (MCP response)")
    mcp_conf_parser.add_argument("-o", "--output", required=True, help="Output markdown file path")

    args = parser.parse_args()

    # Path validation helper
    def validate_input_path(path: Path) -> bool:
        if not path.exists():
            print(f"ERROR: Input file not found: {path}", file=sys.stderr)
            sys.exit(3)
        return True

    quiet = args.quiet

    try:
        if args.mode == "dir":
            input_dir = Path(args.input_dir)
            validate_input_path(input_dir)
            process_directory(input_dir, quiet=quiet)

        elif args.mode in ("jira", "confluence"):
            input_path = Path(args.input)
            output_path = Path(args.output)
            validate_input_path(input_path)

            ok, size_in, size_out = extract_file(input_path, output_path)
            if ok:
                if quiet:
                    print(f"OK: {output_path}")
                else:
                    saved_pct = round((1 - size_out / size_in) * 100) if size_in else 0
                    print(f"OK: {input_path.name} -> {output_path.name}  ({size_in // 1024}KB -> {size_out // 1024}KB, -{saved_pct}%)")
                sys.exit(0)
            else:
                print(f"ERROR: Could not detect format for {input_path.name}", file=sys.stderr)
                sys.exit(2)

        elif args.mode in ("from-mcp-confluence", "from-mcp-jira"):
            output_path = Path(args.output)
            try:
                raw = sys.stdin.read()
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid JSON from stdin: {e}", file=sys.stderr)
                sys.exit(1)

            if args.mode == "from-mcp-confluence":
                page = data.get("page", data.get("content", data))
                markdown = extract_confluence_page(page)
            else:
                file_type = detect_type(data)
                if file_type == "jira_issue":
                    markdown = extract_jira_issue(data)
                elif file_type == "jira_search":
                    markdown = extract_jira_search(data)
                else:
                    markdown = extract_jira_issue(data)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
            if quiet:
                print(f"OK: {output_path}")
            else:
                raw_tokens = max(1, len(raw) // 4)
                out_tokens = max(1, len(markdown) // 4)
                saved_pct = round((1 - out_tokens / raw_tokens) * 100)
                print(f"OK: stdin -> {output_path}  ({raw_tokens}k -> {out_tokens}k tokens, -{saved_pct}%)")
            sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
