#!/usr/bin/env python3
# LIFETIME: revision-REV-005
# Provenance: .claude/skills/publish-confluence/scripts/confluence_publish.py patch
"""One-shot REV-005 surgical patch for Confluence page 7586512902.

Loads `_confluence-storage-current.xml`, applies each REV-005 design change as
a narrow string-replace (CDATA-only for code blocks; table-row-only for tables;
single-paragraph for prose), writes `_confluence-storage-staged.xml`, and
prints a per-edit OK/MISS report. Does NOT push -- operator triggers push
separately after reading the diff.

Each edit asserts exactly one match before replacing. Any mismatch halts.
"""
import re
import sys
from pathlib import Path

# Fixed: path now resolves from repo root (scripts/oneshot/ is 2 levels deep)
HERE = Path(__file__).parent.parent.parent
IN_PATH = HERE / 'memory/features/pwr/pwr-es9-migration/_confluence-storage-current.xml'
OUT_PATH = HERE / 'memory/features/pwr/pwr-es9-migration/_confluence-storage-staged.xml'


def load() -> str:
    return IN_PATH.read_text(encoding='utf-8')


def assert_one(text: str, needle: str, label: str) -> None:
    n = text.count(needle)
    if n != 1:
        raise SystemExit(f'[{label}] expected exactly 1 anchor match, got {n}\n  needle: {needle[:120]!r}')


def replace_once(text: str, needle: str, repl: str, label: str) -> str:
    assert_one(text, needle, label)
    print(f'  OK  {label}')
    return text.replace(needle, repl, 1)


def insert_after(text: str, anchor: str, snippet: str, label: str) -> str:
    assert_one(text, anchor, label)
    print(f'  OK  {label}')
    return text.replace(anchor, anchor + snippet, 1)


def cdata_swap(text: str, anchor_before_cdata: str, new_cdata_body: str, label: str) -> str:
    """Swap the CDATA body of the first ac:structured-macro after `anchor_before_cdata`."""
    start_idx = text.find(anchor_before_cdata)
    if start_idx < 0:
        raise SystemExit(f'[{label}] anchor not found')
    if text.count(anchor_before_cdata) != 1:
        raise SystemExit(f'[{label}] anchor not unique ({text.count(anchor_before_cdata)} matches)')
    cdata_open = '<![CDATA['
    cdata_close = ']]>'
    cdata_start = text.find(cdata_open, start_idx)
    cdata_end = text.find(cdata_close, cdata_start)
    if cdata_start < 0 or cdata_end < 0:
        raise SystemExit(f'[{label}] CDATA brackets not found')
    print(f'  OK  {label}')
    return text[:cdata_start + len(cdata_open)] + new_cdata_body + text[cdata_end:]


# ---------------------------------------------------------------------------
# REV-005 content (no change-log framing, no REV-005 mentions in content)
# ---------------------------------------------------------------------------

GROUP_TYPE_KT_BODY = """package com.powerreviews.datagroup.model

/**
 * Group tier definitions -- naming and tier identity only.
 *
 * Shard topology is NOT carried here. Shard defaults are resolved per (GroupType, DocType)
 * via [TierShardConfig], reflecting that tier ("how big is this group?") and document
 * shape ("how big should this index be for this content?") are independent dimensions.
 *
 * Capacity model: shard-size-driven; per-shard target is externalized via
 * `datagroup.capacity.target-gb-per-shard` (default 40 GB), evaluated per index row
 * as `primaryShards x target-gb-per-shard`. Not stored on the row.
 */
enum class GroupType(val namePrefix: String) {
    SMALL(namePrefix = "sdg"),
    MEDIUM(namePrefix = "mdg"),
    LARGE(namePrefix = "ldg"),
    DEDICATED(namePrefix = "ddg")
}
"""

SHARD_DEFAULTS_KT_BODY = """package com.powerreviews.datagroup.model

/**
 * Immutable shard topology for a single (GroupType, DocType) cell, or for a single
 * per-DocType override on a CreateDataGroupRequest. All three fields are required.
 */
data class ShardDefaults(
    val primaryShards: Int,
    val replicaShards: Int,
    val routingPartitionSize: Int
)
"""

TIER_SHARD_CONFIG_KT_BODY = """package com.powerreviews.datagroup.model

/**
 * Per-tier shard topology matrix -- one enum constant per [GroupType], each carrying
 * the per-[DocType] [ShardDefaults] for that tier (24 cells: 4 tiers x 6 docTypes).
 *
 * Keyed tier-first because the natural call-site loop is "for one group (one tier),
 * iterate the 6 doc types": `TierShardConfig.of(groupType).forDocType(docType)`.
 */
enum class TierShardConfig(
    val groupType: GroupType,
    private val perDocType: Map<DocType, ShardDefaults>
) {
    SMALL(groupType = GroupType.SMALL, perDocType = mapOf(
        DocType.REVIEW to ShardDefaults(36, 1, 2),
        DocType.PRODUCT to ShardDefaults(36, 1, 2),
        DocType.MEDIA to ShardDefaults(36, 1, 2),
        DocType.QUESTION to ShardDefaults(36, 1, 2),
        DocType.SOCIAL_COLLECTION_META to ShardDefaults(5, 1, 1),
        DocType.REGISTRY to ShardDefaults(36, 1, 2)
    )),
    MEDIUM(groupType = GroupType.MEDIUM, perDocType = mapOf(
        DocType.REVIEW to ShardDefaults(36, 1, 2),
        DocType.PRODUCT to ShardDefaults(36, 1, 2),
        DocType.MEDIA to ShardDefaults(36, 1, 2),
        DocType.QUESTION to ShardDefaults(36, 1, 2),
        DocType.SOCIAL_COLLECTION_META to ShardDefaults(5, 1, 1),
        DocType.REGISTRY to ShardDefaults(36, 1, 2)
    )),
    LARGE(groupType = GroupType.LARGE, perDocType = mapOf(
        DocType.REVIEW to ShardDefaults(36, 1, 2),
        DocType.PRODUCT to ShardDefaults(36, 1, 2),
        DocType.MEDIA to ShardDefaults(36, 1, 2),
        DocType.QUESTION to ShardDefaults(36, 1, 2),
        DocType.SOCIAL_COLLECTION_META to ShardDefaults(5, 1, 1),
        DocType.REGISTRY to ShardDefaults(36, 1, 2)
    )),
    DEDICATED(groupType = GroupType.DEDICATED, perDocType = mapOf(
        DocType.REVIEW to ShardDefaults(10, 1, 2),
        DocType.PRODUCT to ShardDefaults(10, 1, 2),
        DocType.MEDIA to ShardDefaults(10, 1, 2),
        DocType.QUESTION to ShardDefaults(10, 1, 2),
        DocType.SOCIAL_COLLECTION_META to ShardDefaults(5, 1, 1),
        DocType.REGISTRY to ShardDefaults(10, 1, 2)
    ));

    fun forDocType(docType: DocType): ShardDefaults =
        perDocType[docType] ?: error("No ShardDefaults for ($name, $docType) -- matrix incomplete")

    companion object {
        fun of(groupType: GroupType): TierShardConfig = valueOf(groupType.name)
    }
}
"""


def main() -> None:
    print('Loading storage...')
    text = load()
    original_len = len(text)

    text = cdata_swap(
        text,
        '<h4 local-id="41bb911569ce"><ac:inline-comment-marker ac:ref="57285a07-df6b-4984-9ecc-c15d8da52925">GroupType.kt</ac:inline-comment-marker></h4>',
        GROUP_TYPE_KT_BODY,
        'GroupType.kt CDATA',
    )

    print(f'\nTotal length: {original_len} -> {len(text)}')
    OUT_PATH.write_text(text, encoding='utf-8')
    print(f'Staged storage written to {OUT_PATH}')


if __name__ == '__main__':
    main()
