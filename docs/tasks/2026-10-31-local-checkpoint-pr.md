---
status: active
updated: 2026-10-31
owner: project-maintainers
---

# Local research checkpoint integration

User requested a PR and merge of current local work before further restructuring.
The starting checkout was `codex/rsi-gate-robustness` at4999ec5, behind current
mainfbef6fd. Public local changes were preserved in checkpoint550e2d5 and integrated
in an isolated checkout. The original dirty checkout and ignored private inputs,
credentials, data and evidence were not moved into this PR.

```text
Local public snapshot + current main
  → preserve canonical controls and frozen copies
  → exact reuse seams + offline checks + evidence index
  → PR review and hosted CI → merge only when passing
```

## Included and preserved

The checkpoint includes management/stage/data skills and SOPs, published research
plans, catalogs, redacted receipts, the single tagged leaderboard, broker paper
preparation and fixed offline tests, and saved-result analysis/report tools.
Licensed source fixtures retain their provenance and notices. Private T11 source,
raw result exports, credentials, market data and local tracking state stay ignored.
No strategy promotion, broker session, new research case or deployment is implied.

Current main's canonical RSI coordinator version2, recovery/adoption fixes,
boundary checks, generated evidence index and tests are retained. Newly preserved
flat research and hosted source templates are frozen by hashes; current imports
use canonical study/control implementations. Existing hosted-only source templates
are artifacts, not importable local runtime modules. Exact paper/research reuse
seams and the SHA-bound pinned-policy loader are documented in architecture.
Historical installed-skill bytes are archived separately; original recovery receipts
are not rewritten to pretend current instructions have identical historical hashes.

## Review and validation

Two read-only perspectives reviewed standards/privacy and user/spec preservation.
Findings fixed: prefix-wide paper seam authorization narrowed to exact resolved
modules; negative loader/seam regressions added; stale active RSI owner paths
corrected. No privacy/source-rights publication blocker was identified by those
heuristic reviews. They are not independent institutional validation.

Preserved local failures: absent-private-artifact links on a clean checkout,
unclassified/frozen import edges, unowned published plans, local-vs-hosted template
import errors, and a historical installed-skill hash mismatch. Corrections retain
original private paths as explicit unpublished provenance, index every published
plan, separate host templates, and archive the historical skill bytes. No old
financial evidence or budget was reopened.

Acceptance requires `make check`, clean-checkout-compatible documentation and
imports, exact-head hosted CI and no unresolved blocking review findings.
Hosted PR/head/merge identities are reported in the handoff; this task does not
claim a merge before GitHub confirms it. Six tests depending on unpublished local
runtime evidence may skip; missing evidence does not become a pass or paper-ready.
The team PNG was regenerated from the merged catalog and visually inspected.
