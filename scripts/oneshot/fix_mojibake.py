#!/usr/bin/env python3
# LIFETIME: single-use (pwr-es9-migration REV-005)
# Provenance: scripts/check_utf8.py (prevention replaces repair long-term)
"""One-shot mojibake cleanup for pwr-es9-migration design TDDs.

Per-line round-trip:
  1. Strip a leading BOM (U+FEFF) if present; restore it after fixing.
  2. Reconstruct the original UTF-8 byte sequence for the line by treating each
     Unicode code point in the mojibake as:
       - ASCII (cp < 0x80)       -> the raw byte
       - Latin-1 (cp < 0x100)    -> the raw byte (covers U+0090, U+0094, U+009D
                                   that CP1252 has no glyph for but that often
                                   appear in box-drawing mojibake)
       - CP1252 special chars    -> cp1252 byte (handles em-dash, ellipsis, etc.)
       - Anything else           -> the char's own UTF-8 encoding (passthrough)
  3. Decode the reconstructed bytes as UTF-8 (strict).
  4. Keep the fixed line only when it has strictly fewer mojibake markers than
     the original. Otherwise pass the original through unchanged.
"""
import os
import re
import sys

RAW_BYTE_SEQUENCES = [
    b'\xe2\x80\x99', b'\xe2\x80\x98',
    b'\xe2\x80\x9c', b'\xe2\x80\x9d',
    b'\xe2\x80\x93', b'\xe2\x80\x94',
    b'\xe2\x80\xa6',
    b'\xe2\x86\x92', b'\xe2\x86\x90',
    b'\xe2\x86\x91', b'\xe2\x86\x93',
    b'\xe2\x86\x94',
    b'\xc3\x97', b'\xc3\xb7',
    b'\xe2\x89\xa5', b'\xe2\x89\xa4',
    b'\xe2\x94\x80', b'\xe2\x94\x82',
    b'\xe2\x94\x8c', b'\xe2\x94\x90',
    b'\xe2\x94\x94', b'\xe2\x94\x98',
    b'\xe2\x94\x9c', b'\xe2\x94\xa4',
    b'\xe2\x94\xac', b'\xe2\x94\xb4',
    b'\xe2\x94\xbc',
]
MARKERS = [r.decode('cp1252', errors='replace') for r in RAW_BYTE_SEQUENCES]
MARKERS = [m for m in MARKERS if m and '�' not in m]


def count_markers(s: str) -> int:
    return sum(s.count(m) for m in MARKERS)


def to_original_bytes(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        cp = ord(ch)
        if cp < 0x100:
            out.append(cp)
        else:
            try:
                out.extend(ch.encode('cp1252', errors='strict'))
            except UnicodeEncodeError:
                out.extend(ch.encode('utf-8'))
    return bytes(out)


def try_fix_line(line: str) -> str:
    bom = ''
    body = line
    if body.startswith('﻿'):
        bom = '﻿'
        body = body[1:]

    before = count_markers(body)
    if before == 0:
        return line

    try:
        recovered = to_original_bytes(body)
        fixed = recovered.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        return line

    if count_markers(fixed) < before:
        return bom + fixed
    return line


def fix_file(path: str) -> tuple:
    with open(path, 'rb') as f:
        raw = f.read()
    text = raw.decode('utf-8', errors='replace')
    before_count = count_markers(text)

    parts = re.split(r'(\r\n|\r|\n)', text)
    fixed_parts = []
    for i, p in enumerate(parts):
        if i % 2 == 0:
            fixed_parts.append(try_fix_line(p))
        else:
            fixed_parts.append(p)
    fixed_text = ''.join(fixed_parts)
    after_count = count_markers(fixed_text)

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(fixed_text)
    return before_count, after_count


def main(argv):
    files = argv[1:] if len(argv) > 1 else [
        'docs/features/pwr/pwr-es9-migration/design/TDD_MASTER.md',
        'docs/features/pwr/pwr-es9-migration/design/TDD_elasticsearch-datagroup-api.md',
        'docs/features/pwr/pwr-es9-migration/design/TDD_elasticsearch-writer.md',
        'docs/features/pwr/pwr-es9-migration/design/TDD_content-publication.md',
        'docs/features/pwr/pwr-es9-migration/design/TDD_distribution-services.md',
        'docs/features/pwr/pwr-es9-migration/design/TDD_readservices-b2c.md',
    ]
    total_before = 0
    total_after = 0
    for path in files:
        if not os.path.exists(path):
            print(f'SKIP (missing): {path}')
            continue
        b, a = fix_file(path)
        total_before += b
        total_after += a
        print(f'{os.path.basename(path):>45}: {b:>5} -> {a:>5} markers')
    print(f'{"TOTAL":>45}: {total_before:>5} -> {total_after:>5} markers')


if __name__ == '__main__':
    main(sys.argv)
