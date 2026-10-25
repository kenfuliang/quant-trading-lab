---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Teams and skills catalog consolidation

Task state: completed. Scope: one canonical discovery catalog, preserving detailed
role contracts, executable instructions and historical evidence.

## Acceptance and changes

- [Teams and skills catalog](../skills.md) owns roster, inventory, routing,
  invocation and readiness. Its installed inventory matches all 22 local skills.
- README, AGENTS, documentation map, architecture, research handoff and project
  router link to that owner instead of keeping competing rosters/counts.
- [Advisory contracts](../advisory-team.md) retain detailed responsibilities,
  collaboration and historical public-source research. Discovery hierarchy,
  invocation mapping and planned specializations moved to the catalog.
- The existing documentation check verifies each installed skill is cataloged
  once, each catalog entry exists, and folder/frontmatter identities match.
  Four fixture tests cover valid inventory, unlisted skills, missing/duplicate
  entries and identity mismatch. This check validates inventory, not financial
  performance, skill usefulness or role independence.
- Historical task receipts, datasets and financial run artifacts were preserved.

## Verification

`make check` passed: documentation/link/catalog parity, dependency consistency,
and 220 offline tests. Documentation was checked again after final catalog links
and this receipt. No broker operations, model training, financial trials,
commits or publication were performed.
