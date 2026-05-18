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
confluence_publish.py — Markdown pre-processor for Confluence publishing.

Converts a pipeline artifact (PRD, TDD) from Markdown to Confluence storage
format. Handles:
  - Pipeline frontmatter stripping
  - Table conversion
  - Mermaid diagram wrapping (code macro with label)
  - Standard Markdown elements (headers, bold, italic, code, lists, HR)
  - Pipeline-internal reference removal

Usage:
  sh scripts/confluence_publish.py preprocess <input.md> [--output <out.xml>]
"""

import re
import sys
import argparse
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Frontmatter stripping
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    """
    Remove pipeline frontmatter block from the top of the document.
    Frontmatter is everything from the start up to and including the first
    '---' separator line.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "---":
            return "".join(lines[i + 1:]).lstrip("\n")
    return text


# ---------------------------------------------------------------------------
# Mermaid block extraction and replacement
# ---------------------------------------------------------------------------

MERMAID_PLACEHOLDER = "MERMAID_BLOCK_{index}"

# Maps diagram type keyword to a human-readable label
DIAGRAM_LABELS = {
    "graph":       "📊 Diagram",
    "flowchart":   "📊 Flow Diagram",
    "sequenceDiagram": "📋 Sequence Diagram",
    "stateDiagram": "🔄 State Diagram",
    "gantt":       "📅 Timeline",
    "erDiagram":   "🗄️ Data Model",
    "classDiagram": "🏗️ Class Diagram",
}


def _detect_label(mermaid_body: str) -> str:
    first_line = mermaid_body.strip().splitlines()[0].strip() if mermaid_body.strip() else ""
    for keyword, label in DIAGRAM_LABELS.items():
        if first_line.startswith(keyword):
            return label
    return "📊 Diagram"


def extract_mermaid_blocks(text: str):
    """
    Extract all ```mermaid blocks, replace with placeholders.
    Returns (processed_text, list_of_mermaid_bodies).
    """
    blocks = []
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

    def replacer(match):
        idx = len(blocks)
        blocks.append(match.group(1))
        return MERMAID_PLACEHOLDER.format(index=idx)

    processed = pattern.sub(replacer, text)
    return processed, blocks


def mermaid_to_confluence_macro(body: str, label: str) -> str:
    """
    Wrap a Mermaid diagram body in a Confluence code macro with a label panel.
    """
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<p><strong>{label}</strong></p>'
        f'<ac:structured-macro ac:name="code">'
        f'<ac:parameter ac:name="language">none</ac:parameter>'
        f'<ac:parameter ac:name="title">{label}</ac:parameter>'
        f'<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body>'
        f'</ac:structured-macro>'
    )


def restore_mermaid_blocks(text: str, blocks: list) -> str:
    for idx, body in enumerate(blocks):
        label = _detect_label(body)
        macro = mermaid_to_confluence_macro(body, label)
        text = text.replace(MERMAID_PLACEHOLDER.format(index=idx), macro)
    return text


# ---------------------------------------------------------------------------
# Code block extraction and replacement
# ---------------------------------------------------------------------------

CODE_PLACEHOLDER = "CODE_BLOCK_{index}"


def extract_code_blocks(text: str):
    blocks = []
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

    def replacer(match):
        idx = len(blocks)
        lang = match.group(1) or "none"
        code = match.group(2)
        blocks.append((lang, code))
        return CODE_PLACEHOLDER.format(index=idx)

    processed = pattern.sub(replacer, text)
    return processed, blocks


def restore_code_blocks(text: str, blocks: list) -> str:
    for idx, (lang, code) in enumerate(blocks):
        macro = (
            f'<ac:structured-macro ac:name="code">'
            f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
            f'<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>'
            f'</ac:structured-macro>'
        )
        text = text.replace(CODE_PLACEHOLDER.format(index=idx), macro)
    return text


# ---------------------------------------------------------------------------
# Table conversion
# ---------------------------------------------------------------------------

def convert_tables(text: str) -> str:
    """Convert Markdown tables to Confluence storage HTML tables."""
    lines = text.splitlines(keepends=True)
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect table: line with | that is followed by a separator line
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s\-:|]+\|", lines[i + 1]):
            table_lines = [line]
            i += 1
            # Skip separator
            i += 1
            # Collect body rows
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1

            result.append(_build_table(table_lines))
        else:
            result.append(line)
            i += 1

    return "".join(result)


def _parse_row(line: str) -> list:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _build_table(lines: list) -> str:
    if not lines:
        return ""

    header_cells = _parse_row(lines[0])
    body_rows = [_parse_row(l) for l in lines[1:]] if len(lines) > 1 else []

    html = '<table><tbody>'

    # Header row
    html += '<tr>'
    for cell in header_cells:
        html += f'<th><strong>{_inline_md(cell)}</strong></th>'
    html += '</tr>'

    # Body rows
    for row in body_rows:
        html += '<tr>'
        for cell in row:
            html += f'<td>{_inline_md(cell)}</td>'
        html += '</tr>'

    html += '</tbody></table>\n'
    return html


# ---------------------------------------------------------------------------
# Inline Markdown conversion
# ---------------------------------------------------------------------------

def _inline_md(text: str) -> str:
    """Convert inline Markdown (bold, italic, inline code, links) to HTML."""
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # Links
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    return text


# ---------------------------------------------------------------------------
# Block-level Markdown conversion
# ---------------------------------------------------------------------------

def convert_markdown(text: str) -> str:
    lines = text.splitlines(keepends=True)
    result = []
    in_list = None  # 'ul' or 'ol'

    def close_list():
        nonlocal in_list
        if in_list:
            result.append(f'</{in_list}>\n')
            in_list = None

    for line in lines:
        stripped = line.rstrip("\n")

        # Horizontal rule
        if re.match(r"^---+$", stripped) or re.match(r"^\*\*\*+$", stripped):
            close_list()
            result.append("<hr/>\n")
            continue

        # Headers
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            close_list()
            level = len(m.group(1))
            content = _inline_md(m.group(2))
            result.append(f"<h{level}>{content}</h{level}>\n")
            continue

        # Unordered list
        m = re.match(r"^[-*]\s+(.+)$", stripped)
        if m:
            if in_list != "ul":
                close_list()
                result.append("<ul>\n")
                in_list = "ul"
            result.append(f"<li>{_inline_md(m.group(1))}</li>\n")
            continue

        # Ordered list
        m = re.match(r"^\d+\.\s+(.+)$", stripped)
        if m:
            if in_list != "ol":
                close_list()
                result.append("<ol>\n")
                in_list = "ol"
            result.append(f"<li>{_inline_md(m.group(1))}</li>\n")
            continue

        # Blank line
        if not stripped:
            close_list()
            result.append("\n")
            continue

        # Already converted (macro placeholders, table HTML)
        if stripped.startswith("<") or "MERMAID_BLOCK_" in stripped or "CODE_BLOCK_" in stripped:
            close_list()
            result.append(line)
            continue

        # Regular paragraph
        close_list()
        result.append(f"<p>{_inline_md(stripped)}</p>\n")

    close_list()
    return "".join(result)


# ---------------------------------------------------------------------------
# Pipeline reference cleanup
# ---------------------------------------------------------------------------

PIPELINE_REFS = [
    r"FEATURE_DRAFT\.md",
    r"DISCOVERY_NOTES\.md",
    r"PRD_REVIEW\.md",
    r"\*\*Upstream Inputs:\*\*.*",
    r"\*\*Feature Folder:\*\*.*",
    r"\*\*Pipeline Version:\*\*.*",
    r"\*\*AI Co-Author:\*\*.*",
]


def remove_pipeline_refs(text: str) -> str:
    for pattern in PIPELINE_REFS:
        text = re.sub(pattern, "", text)
    # Clean up blank lines left behind
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def preprocess(input_path: str, output_path: str = None) -> str:
    path = Path(input_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    text = path.read_text(encoding="utf-8")

    # 1. Strip frontmatter
    text = strip_frontmatter(text)

    # 2. Remove pipeline references
    text = remove_pipeline_refs(text)

    # 3. Extract Mermaid blocks (protect from further processing)
    text, mermaid_blocks = extract_mermaid_blocks(text)

    # 4. Extract code blocks (protect from further processing)
    text, code_blocks = extract_code_blocks(text)

    # 5. Convert tables
    text = convert_tables(text)

    # 6. Convert remaining Markdown
    text = convert_markdown(text)

    # 7. Restore code blocks
    text = restore_code_blocks(text, code_blocks)

    # 8. Restore Mermaid blocks
    text = restore_mermaid_blocks(text, mermaid_blocks)

    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        print(f"[OK] Processed: {output_path}")
    else:
        # Write to temp file and print path
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        print(tmp.name)

    return text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Confluence Markdown pre-processor")
    parser.add_argument("action", choices=["preprocess"], help="Action to perform")
    parser.add_argument("input", help="Input Markdown file path")
    parser.add_argument("--output", help="Output file path (default: temp file)")
    args = parser.parse_args()

    if args.action == "preprocess":
        try:
            preprocess(args.input, args.output)
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
