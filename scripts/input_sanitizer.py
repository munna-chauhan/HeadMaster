#!/usr/bin/env python3
"""
Input Sanitizer — detects and neutralizes prompt injection patterns in external text.

Applied at two boundaries:
  1. jira_ops.py _sanitize_response() — sanitizes raw API response strings
  2. input_extractor.py — sanitizes extracted markdown before writing .md files

Defense strategy:
  - Detect known injection patterns (instruction overrides, role hijacking, etc.)
  - Neutralize by wrapping suspicious lines in visible markers
  - Log all detections for audit trail
  - Never silently drop content — always preserve original meaning while disarming

Usage:
    from scripts.input_sanitizer import sanitize_external_input, fence_external_content
"""

import re
from dataclasses import dataclass, field
from typing import List

# Patterns that indicate prompt injection attempts.
# Each tuple: (compiled_regex, severity, description)
_INJECTION_PATTERNS = [
    # Direct instruction overrides
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)",
                re.IGNORECASE), "HIGH", "instruction_override"),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
                re.IGNORECASE), "HIGH", "instruction_override"),
    (re.compile(r"forget\s+(everything|all|what)\s+(you|I)\s+(told|said|instructed)",
                re.IGNORECASE), "HIGH", "instruction_override"),

    # Role/persona hijacking
    (re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE), "HIGH", "role_hijack"),
    (re.compile(r"act\s+as\s+(a|an|the|if)\s+", re.IGNORECASE), "MEDIUM", "role_hijack"),
    (re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE), "HIGH", "role_hijack"),
    (re.compile(r"switch\s+to\s+.{0,20}mode", re.IGNORECASE), "MEDIUM", "role_hijack"),

    # System prompt extraction
    (re.compile(r"(print|show|reveal|output|display|repeat)\s+(your|the)\s+(system\s+prompt|instructions|rules)",
                re.IGNORECASE), "HIGH", "prompt_extraction"),
    (re.compile(r"what\s+(are|is)\s+your\s+(system\s+prompt|instructions|rules|constraints)",
                re.IGNORECASE), "MEDIUM", "prompt_extraction"),

    # Dangerous action directives
    (re.compile(r"(delete|remove|drop|truncate|destroy)\s+(all\s+)?(files?|database|table|repo|branch)",
                re.IGNORECASE), "HIGH", "destructive_directive"),
    (re.compile(r"push\s+(to|--force)\s+main", re.IGNORECASE), "HIGH", "destructive_directive"),
    (re.compile(r"rm\s+-rf", re.IGNORECASE), "HIGH", "destructive_directive"),
    (re.compile(r"git\s+push\s+.*--force", re.IGNORECASE), "HIGH", "destructive_directive"),

    # Encoded/obfuscated injection attempts
    (re.compile(r"base64[:\s]+(decode|encode)", re.IGNORECASE), "MEDIUM", "obfuscation"),
    (re.compile(r"\\x[0-9a-fA-F]{2}", re.IGNORECASE), "LOW", "obfuscation"),

    # Prompt delimiter manipulation
    (re.compile(r"</?system>", re.IGNORECASE), "HIGH", "delimiter_manipulation"),
    (re.compile(r"\[INST\]|\[/INST\]", re.IGNORECASE), "HIGH", "delimiter_manipulation"),
    (re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE), "HIGH", "delimiter_manipulation"),
    (re.compile(r"```system", re.IGNORECASE), "MEDIUM", "delimiter_manipulation"),
]


@dataclass
class SanitizationResult:
    """Result of sanitizing a text block."""
    sanitized_text: str
    detections: List[dict] = field(default_factory=list)
    was_modified: bool = False


def sanitize_external_input(text: str, source: str = "unknown", **kwargs) -> str:
    """Sanitize external text — drop-in replacement for the no-op fallback in jira_ops.py.

    Returns sanitized text. Injection patterns are neutralized by prefixing
    suspicious lines with a visible marker so downstream agents can see the
    original content but are warned not to treat it as instructions.
    """
    if not text or not isinstance(text, str):
        return text

    result = _sanitize(text, source)
    return result.sanitized_text


def sanitize_and_report(text: str, source: str = "unknown") -> SanitizationResult:
    """Sanitize and return full detection report. Used by input_extractor for logging."""
    if not text or not isinstance(text, str):
        return SanitizationResult(sanitized_text=text or "")
    return _sanitize(text, source)


def fence_external_content(content: str, source: str, field_name: str = "content") -> str:
    """Wrap external content in data-fence markers for artifact embedding.

    These markers create a machine-readable trust boundary that agent prompts
    are instructed to treat as data-only.
    """
    return (
        f"<!-- EXTERNAL-DATA-START source=\"{source}\" field=\"{field_name}\" -->\n"
        f"{content}\n"
        f"<!-- EXTERNAL-DATA-END -->"
    )


def _sanitize(text: str, source: str) -> SanitizationResult:
    """Core sanitization logic."""
    lines = text.split("\n")
    output_lines = []
    detections = []
    modified = False

    for line_num, line in enumerate(lines, 1):
        flagged = False
        for pattern, severity, category in _INJECTION_PATTERNS:
            if pattern.search(line):
                detections.append({
                    "line": line_num,
                    "severity": severity,
                    "category": category,
                    "pattern": pattern.pattern[:60],
                    "source": source,
                    "snippet": line[:120],
                })
                if not flagged and severity in ("HIGH", "MEDIUM"):
                    output_lines.append(f"[⚠ SANITIZED — possible injection from {source}] {line}")
                    flagged = True
                    modified = True
                break

        if not flagged:
            output_lines.append(line)

    return SanitizationResult(
        sanitized_text="\n".join(output_lines),
        detections=detections,
        was_modified=modified,
    )
