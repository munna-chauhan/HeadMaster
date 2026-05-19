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
confluence_publish.py -- Markdown pre-processor and Confluence publisher.

Actions:
  preprocess  Convert Markdown to Confluence storage XML (local, no network)
  fetch       Download current storage XML from a page
  update      Replace a page's body with a storage XML file
  create      Create a new child page from a storage XML file
  patch       Apply a YAML manifest of surgical edits to a storage XML file
  validate    Check storage XML for common structural issues

Usage:
  sh confluence_publish.py preprocess <input.md> [--output <out.xml>]
  sh confluence_publish.py fetch <page-id> [--output <out.xml>]
  sh confluence_publish.py update <page-id> <body.xml> <title>
  sh confluence_publish.py create <parent-id> <body.xml> <title>
  sh confluence_publish.py patch <input.xml> <manifest.yml> [--output <out.xml>]
  sh confluence_publish.py validate <file.xml>

Auth (for network actions): ATLASSIAN_DOMAIN, JIRA_USER_EMAIL, JIRA_API_TOKEN env vars.
"""

import json
import os
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

CODE_PLACEHOLDER = "CODE_BLOCK_{index}_END"


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


# Languages natively supported by Confluence code macro. Unsupported languages fall back to "none".
_CONFLUENCE_LANGUAGES = {
    "java", "javascript", "js", "typescript", "ts", "python", "py",
    "xml", "html", "sql", "bash", "sh", "shell", "groovy", "scala",
    "json", "yaml", "yml", "kotlin", "swift", "ruby", "go", "rust",
    "cpp", "c", "csharp", "cs", "php", "perl", "none",
}

_LANG_ALIASES = {
    "js": "javascript", "ts": "typescript", "py": "python",
    "sh": "bash", "shell": "bash", "yml": "yaml",
    "cs": "csharp", "hcl": "none", "terraform": "none",
    "properties": "none", "text": "none", "txt": "none",
    "mermaid": "none",
}


def _normalise_lang(lang: str) -> str:
    lang = lang.lower().strip()
    lang = _LANG_ALIASES.get(lang, lang)
    return lang if lang in _CONFLUENCE_LANGUAGES else "none"


def restore_code_blocks(text: str, blocks: list) -> str:
    for idx, (lang, code) in enumerate(blocks):
        cf_lang = _normalise_lang(lang)
        macro = (
            f'<ac:structured-macro ac:name="code" ac:schema-version="1">'
            f'<ac:parameter ac:name="language">{cf_lang}</ac:parameter>'
            f'<ac:parameter ac:name="breakoutMode">full-width</ac:parameter>'
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
    para_buf = []   # accumulates consecutive paragraph lines

    def close_list():
        nonlocal in_list
        if in_list:
            result.append(f'</{in_list}>\n')
            in_list = None

    def flush_para():
        if para_buf:
            result.append(f"<p>{' '.join(para_buf)}</p>\n")
            para_buf.clear()

    for line in lines:
        stripped = line.rstrip("\n")

        # Horizontal rule
        if re.match(r"^---+$", stripped) or re.match(r"^\*\*\*+$", stripped):
            flush_para()
            close_list()
            result.append("<hr/>\n")
            continue

        # Headers
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            flush_para()
            close_list()
            level = len(m.group(1))
            content = _inline_md(m.group(2))
            result.append(f"<h{level}>{content}</h{level}>\n")
            continue

        # Unordered list
        m = re.match(r"^[-*]\s+(.+)$", stripped)
        if m:
            flush_para()
            if in_list != "ul":
                close_list()
                result.append("<ul>\n")
                in_list = "ul"
            result.append(f"<li>{_inline_md(m.group(1))}</li>\n")
            continue

        # Ordered list
        m = re.match(r"^\d+\.\s+(.+)$", stripped)
        if m:
            flush_para()
            if in_list != "ol":
                close_list()
                result.append("<ol>\n")
                in_list = "ol"
            result.append(f"<li>{_inline_md(m.group(1))}</li>\n")
            continue

        # Blank line
        if not stripped:
            flush_para()
            close_list()
            result.append("\n")
            continue

        # Already converted (macro placeholders, table HTML)
        if stripped.startswith("<") or "MERMAID_BLOCK_" in stripped or "CODE_BLOCK_" in stripped:
            flush_para()
            close_list()
            result.append(line)
            continue

        # Regular paragraph line — accumulate
        para_buf.append(_inline_md(stripped))

    flush_para()
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
# Confluence HTTP helpers
# ---------------------------------------------------------------------------

def _auth():
    domain = os.environ.get("ATLASSIAN_DOMAIN", "")
    email = os.environ.get("JIRA_USER_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    if not (domain and email and token):
        print("[ERROR] Missing ATLASSIAN_DOMAIN / JIRA_USER_EMAIL / JIRA_API_TOKEN", file=sys.stderr)
        sys.exit(1)
    return domain, (email, token)


def _get_page(domain: str, auth: tuple, page_id: str, verify: bool = True) -> dict:
    try:
        import urllib3
        if not verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        import requests
    except ImportError:
        print("[ERROR] 'requests' library not installed", file=sys.stderr)
        sys.exit(1)
    headers = {"Accept": "application/json"}
    r = requests.get(
        f"https://{domain}/wiki/api/v2/pages/{page_id}",
        auth=auth, headers=headers, timeout=30, verify=verify,
    )
    if r.status_code != 200:
        print(f"[ERROR] GET page {page_id}: HTTP {r.status_code}\n{r.text[:500]}", file=sys.stderr)
        sys.exit(1)
    return r.json()


def fetch(page_id: str, output_path: str = None, verify: bool = True) -> str:
    """Download current storage XML for a Confluence page."""
    domain, auth = _auth()
    try:
        import requests
    except ImportError:
        print("[ERROR] 'requests' library not installed", file=sys.stderr)
        sys.exit(1)
    headers = {"Accept": "application/json"}
    r = requests.get(
        f"https://{domain}/wiki/api/v2/pages/{page_id}?body-format=storage",
        auth=auth, headers=headers, timeout=30, verify=verify,
    )
    if r.status_code != 200:
        print(f"[ERROR] fetch {page_id}: HTTP {r.status_code}\n{r.text[:500]}", file=sys.stderr)
        sys.exit(1)
    body = r.json().get("body", {}).get("storage", {}).get("value", "")
    if output_path:
        Path(output_path).write_text(body, encoding="utf-8")
        print(f"[OK] Fetched page {page_id} -> {output_path}")
    else:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8")
        tmp.write(body)
        tmp.close()
        print(tmp.name)
    return body


def update(page_id: str, body_path: str, title: str, verify: bool = True) -> None:
    """Replace a Confluence page's body with a storage XML file."""
    domain, auth = _auth()
    try:
        import requests
    except ImportError:
        print("[ERROR] 'requests' library not installed", file=sys.stderr)
        sys.exit(1)
    body = Path(body_path).read_text(encoding="utf-8")
    page = _get_page(domain, auth, page_id, verify=verify)
    cur_version = page["version"]["number"]
    payload = {
        "id": page_id,
        "status": "current",
        "title": title,
        "body": {"representation": "storage", "value": body},
        "version": {"number": cur_version + 1},
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    r = requests.put(
        f"https://{domain}/wiki/api/v2/pages/{page_id}",
        auth=auth, headers=headers, data=json.dumps(payload), timeout=60, verify=verify,
    )
    if r.status_code not in (200, 204):
        print(f"[ERROR] update {page_id}: HTTP {r.status_code}\n{r.text[:1500]}", file=sys.stderr)
        sys.exit(1)
    result = r.json()
    new_ver = result.get("version", {}).get("number")
    web_url = result.get("_links", {}).get("webui", "")
    base = f"https://{domain}"
    print(f"[OK] Updated page {page_id} to v{new_ver}: {base}/wiki{web_url}" if web_url else f"[OK] Updated page {page_id} to v{new_ver}")


def create(parent_id: str, body_path: str, title: str, space_key: str = None, verify: bool = True) -> None:
    """Create a new child page under parent_id from a storage XML file."""
    domain, auth = _auth()
    try:
        import requests
    except ImportError:
        print("[ERROR] 'requests' library not installed", file=sys.stderr)
        sys.exit(1)
    body = Path(body_path).read_text(encoding="utf-8")
    if not space_key:
        # Derive space_key from parent page
        parent = _get_page(domain, auth, parent_id, verify=verify)
        space_key = parent.get("spaceId", "")
    payload = {
        "title": title,
        "parentId": parent_id,
        "spaceId": space_key,
        "body": {"representation": "storage", "value": body},
        "status": "current",
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    r = requests.post(
        f"https://{domain}/wiki/api/v2/pages",
        auth=auth, headers=headers, data=json.dumps(payload), timeout=60, verify=verify,
    )
    if r.status_code not in (200, 201):
        print(f"[ERROR] create under {parent_id}: HTTP {r.status_code}\n{r.text[:1500]}", file=sys.stderr)
        sys.exit(1)
    result = r.json()
    page_id = result.get("id")
    web_url = result.get("_links", {}).get("webui", "")
    base = f"https://{domain}"
    print(f"[OK] Created page {page_id}: {base}/wiki{web_url}" if web_url else f"[OK] Created page {page_id}")


def patch(input_path: str, manifest_path: str, output_path: str = None) -> str:
    """Apply a YAML manifest of surgical edits to a Confluence storage XML file.

    Manifest format (YAML list of edits):
      - kind: cdata_swap
        anchor: <unique string before the CDATA>
        body: <new CDATA content>
        label: <description for log>
      - kind: replace_once
        needle: <exact string to replace>
        replacement: <replacement string>
        label: <description for log>
      - kind: insert_after
        anchor: <unique string to insert after>
        snippet: <content to insert>
        label: <description for log>
    """
    try:
        import yaml
    except ImportError:
        print("[ERROR] 'pyyaml' library not installed", file=sys.stderr)
        sys.exit(1)

    text = Path(input_path).read_text(encoding="utf-8")
    edits = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))

    for edit in edits:
        kind = edit.get("kind")
        label = edit.get("label", kind)
        if kind == "cdata_swap":
            text = _patch_cdata_swap(text, edit["anchor"], edit["body"], label)
        elif kind == "replace_once":
            text = _patch_replace_once(text, edit["needle"], edit["replacement"], label)
        elif kind == "insert_after":
            text = _patch_insert_after(text, edit["anchor"], edit["snippet"], label)
        else:
            print(f"[ERROR] Unknown patch kind: {kind!r}", file=sys.stderr)
            sys.exit(1)

    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        print(f"[OK] Patched: {output_path}")
    else:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        print(tmp.name)
    return text


def _patch_cdata_swap(text: str, anchor: str, new_body: str, label: str) -> str:
    idx = text.find(anchor)
    if idx < 0:
        print(f"[ERROR] [{label}] anchor not found", file=sys.stderr)
        sys.exit(1)
    if text.count(anchor) != 1:
        print(f"[ERROR] [{label}] anchor not unique ({text.count(anchor)} matches)", file=sys.stderr)
        sys.exit(1)
    cdata_start = text.find("<![CDATA[", idx)
    cdata_end = text.find("]]>", cdata_start)
    if cdata_start < 0 or cdata_end < 0:
        print(f"[ERROR] [{label}] CDATA brackets not found after anchor", file=sys.stderr)
        sys.exit(1)
    print(f"  OK  {label}")
    return text[:cdata_start + len("<![CDATA[")] + new_body + text[cdata_end:]


def _patch_replace_once(text: str, needle: str, replacement: str, label: str) -> str:
    n = text.count(needle)
    if n != 1:
        print(f"[ERROR] [{label}] expected exactly 1 match, got {n}", file=sys.stderr)
        sys.exit(1)
    print(f"  OK  {label}")
    return text.replace(needle, replacement, 1)


def _patch_insert_after(text: str, anchor: str, snippet: str, label: str) -> str:
    n = text.count(anchor)
    if n != 1:
        print(f"[ERROR] [{label}] expected exactly 1 match, got {n}", file=sys.stderr)
        sys.exit(1)
    print(f"  OK  {label}")
    return text.replace(anchor, anchor + snippet, 1)


def validate(file_path: str) -> bool:
    """Check a Confluence storage XML file for structural issues.

    Checks:
      - UTF-8 validity
      - Balanced CDATA markers
      - Balanced <ac:structured-macro> tags
      - local-id uniqueness
    """
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        print(f"[FAIL] UTF-8 decode error: {e}", file=sys.stderr)
        return False

    errors = []

    # CDATA balance
    opens = text.count("<![CDATA[")
    closes = text.count("]]>")
    if opens != closes:
        errors.append(f"Unbalanced CDATA: {opens} open, {closes} close")

    # ac:structured-macro balance
    macro_opens = len(re.findall(r"<ac:structured-macro\b", text))
    macro_closes = text.count("</ac:structured-macro>")
    if macro_opens != macro_closes:
        errors.append(f"Unbalanced ac:structured-macro: {macro_opens} open, {macro_closes} close")

    # local-id uniqueness
    local_ids = re.findall(r'local-id="([^"]+)"', text)
    seen: set = set()
    dupes: set = set()
    for lid in local_ids:
        if lid in seen:
            dupes.add(lid)
        seen.add(lid)
    if dupes:
        errors.append(f"Duplicate local-id values: {sorted(dupes)}")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        return False

    print(f"[OK] {file_path}: validation passed")
    return True


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
    parser = argparse.ArgumentParser(description="Confluence Markdown publisher")
    sub = parser.add_subparsers(dest="action", required=True)

    p_pre = sub.add_parser("preprocess", help="Convert Markdown to Confluence storage XML")
    p_pre.add_argument("input", help="Input Markdown file")
    p_pre.add_argument("--output", help="Output path (default: temp file)")

    p_fetch = sub.add_parser("fetch", help="Download page storage XML")
    p_fetch.add_argument("page_id", help="Confluence page ID")
    p_fetch.add_argument("--output", help="Output path (default: temp file)")
    p_fetch.add_argument("--no-verify", action="store_true", help="Disable TLS verification (corporate proxies)")

    p_upd = sub.add_parser("update", help="Replace page body")
    p_upd.add_argument("page_id", help="Confluence page ID")
    p_upd.add_argument("body", help="Storage XML file path")
    p_upd.add_argument("title", help="Page title")
    p_upd.add_argument("--no-verify", action="store_true")

    p_cre = sub.add_parser("create", help="Create new child page")
    p_cre.add_argument("parent_id", help="Parent page ID")
    p_cre.add_argument("body", help="Storage XML file path")
    p_cre.add_argument("title", help="Page title")
    p_cre.add_argument("--space-key", help="Confluence space key (derived from parent if omitted)")
    p_cre.add_argument("--no-verify", action="store_true")

    p_patch = sub.add_parser("patch", help="Apply surgical edits via YAML manifest")
    p_patch.add_argument("input", help="Input storage XML file")
    p_patch.add_argument("manifest", help="YAML manifest of edits")
    p_patch.add_argument("--output", help="Output path (default: temp file)")

    p_val = sub.add_parser("validate", help="Check storage XML for structural issues")
    p_val.add_argument("input", help="Storage XML file to validate")

    args = parser.parse_args()

    try:
        if args.action == "preprocess":
            preprocess(args.input, args.output)
        elif args.action == "fetch":
            fetch(args.page_id, args.output, verify=not args.no_verify)
        elif args.action == "update":
            update(args.page_id, args.body, args.title, verify=not args.no_verify)
        elif args.action == "create":
            create(args.parent_id, args.body, args.title, space_key=args.space_key, verify=not args.no_verify)
        elif args.action == "patch":
            patch(args.input, args.manifest, args.output)
        elif args.action == "validate":
            ok = validate(args.input)
            sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
