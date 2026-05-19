# scripts/oneshot/ -- One-Shot Script Policy

Scripts here are single-use or revision-scoped tools that do not belong in the
main skill pipeline. Each script must declare:

- `LIFETIME`: when this script expires (`single-use`, `revision-{REV-N}`, `until-{date}`)
- `Provenance`: the canonical skill or script that will absorb this work long-term

## Lifecycle rules

1. Scripts are named `{purpose}.py` (no `_oneshot_` prefix needed inside this dir).
2. A script is stale when its LIFETIME condition is met (revision closed, date passed).
3. Stale scripts must be deleted before merge to main.
4. `sh scripts/audit_inventory.py` reports stale one-shots when extended to cover this dir.

## Current scripts

| Script | LIFETIME | Provenance |
|---|---|---|
| fix_mojibake.py | single-use (pwr-es9-migration) | `scripts/check_utf8.py` (prevention replaces repair) |
| confluence_push.py | revision-REV-005 | `.claude/skills/publish-confluence/scripts/confluence_publish.py update` |
| confluence_patch_rev005.py | revision-REV-005 | `.claude/skills/publish-confluence/scripts/confluence_publish.py patch` |
