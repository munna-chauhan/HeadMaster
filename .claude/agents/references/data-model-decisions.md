# Data Model Entity Classification

For every entity (Review, Reviewer, SamplingCampaign, etc.):

## Decision Table

| Entity | Type | Reason | Lineage? | Governance |
|--------|------|--------|----------|-----------|
| Review | First-class | Independent lifecycle, moderation queue, audit trail | Yes | Separate RBAC, versioning |
| Reviewer | Sub-entity | Managed via Review lifecycle, no independent state | No | Read-only reference |

## Classification Rules

**First-class (separate table)** if:
- Has independent governance (own RBAC, audit log, versioning)
- Needs separate moderation workflow
- Is referenced by multiple entities (not just parent)
- Requires lineage tracking (who changed what, when, why)

**Sub-entity (JSONB field)** if:
- Lifecycle is coupled to parent (created/deleted with parent)
- No independent governance needed
- Single-parent reference only
- No provenance tracking required

## Provenance Enforcement

At service contract level (Zod), not database triggers:

```typescript
// If Review has SCRAPED_DSA provenance, it cannot be:
// - displayed to consumers (U1_RENDER_CONSUMER)
// - aggregated in public stats (U3_RENDER_AGGREGATE)
// - but CAN be used for AI input (U4_AI_INPUT)

isPermittedUse(provenance, useClass) → boolean
```

Enforce at design time. Document in ADR-X.