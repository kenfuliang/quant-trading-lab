---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Generated research evidence index and structural review

Work status: offline verification complete; hosted CI follows publication.
Follow-up to PR #6 head `bb3477cdcfc33675415dff3c55d9095f5fd9925e`.
[Architecture](../architecture.md#research-evidence-index) owns the index contract;
[documentation conventions](../README.md) own navigation;
[receipt](evidence/2026-10-27-research-evidence-index.json) records verification.
No strategy selection, new research cycle or financial attempt is part of this task.

## Scope and acceptance

- Curate 13 study/diagnostic entries with plans, results, failures and lessons.
  Cover all 12 published JSON plans exactly once. Missing/local-only evidence is
  explicit; receipts/narratives are distinguished from raw financial artifacts.
- Generate deterministic Markdown/JSON views from the registry and existing source
  files, with per-reference hashes and separately listed unassigned supporting records.
- Preserve existing study plans, task/receipt evidence, reports, source inputs and
  the 327 protected files; no silent historical edit, trial reset or local-data import.
- CI rejects missing references/anchors, invalid registry fields, duplicate owners,
  unowned new plans, changed inputs/stale output and hand-edited generated content.
- Failure tests demonstrate nonzero exit through the actual Make CI target;
  verification mode does not write and private/local files do not affect output.
- Update README/docs navigation and workflow without rewriting the cycle register.
  Run full offline checks and verify the exact published PR commit's hosted CI.

## Method and failure/recovery behavior

The registry is a curated pointer map; machine discovery inventories all plans and
unassigned task/receipt files, rather than guessing study associations or outcomes.
Generation validates first and writes only its two derived views. Repeating it
preserves all source files and produces identical bytes. On interruption or drift,
regenerate views; preserve the original inputs and failed evidence.
Rollback reverts this additive generator, registry, views, tests and Make/docs
routing. No data, ledger, tracking store or dependency migration is required.

## Verification

`make check` passed 411 tests, checks for 93 documentation files, the boundary gate
for 57 current modules and the index gate (13 entries, 12 plans, zero unowned plans).
All 403 existing protected/research evidence files checked remain unchanged,
including the 327 frozen files and the compatibility manifest. Failure-injection
tests demonstrate stale-view CI failure; source and generated-output drift, missing
anchors, coverage gaps, invalid references, circular derived-view citations and duplicate ownership fail closed.

## Rescore

Same subjective engineering rubric and weights as the previous review. The weighted
score moves from **7.8 to 8.1/10**. Discoverability improves through a cross-study
entrypoint; content structure and automated checks improve through mandatory roles,
availability reasons, plan coverage, source hashes and tested drift detection.
No score increase is awarded for dependency layers, source ownership, preservation,
scientific completeness, instrument coverage or restore proof.

| Perspective | Weight | Before | After |
| --- | --- | --- | --- |
| Responsibility and ownership | 15% | 8.5 | 8.5 |
| Dependency boundaries | 15% | 8.5 | 8.5 |
| Discoverability and onboarding | 10% | 6.5 | 8 |
| Frozen evidence preservation | 15% | 9 | 9 |
| Single source of truth | 10% | 8 | 8 |
| Content and report structure | 10% | 8 | 8.5 |
| Automated structural checks | 10% | 8 | 8.5 |
| Growth across research families | 10% | 6 | 6 |
| Evidence recovery and portability | 5% | 5 | 5 |

## Lesson and remaining gaps

A useful index makes unavailable evidence visible instead of manufacturing complete
study dossiers. Linking records does not independently validate their claims or
reproduce their referenced local bundles. General restore proof, contributor
licensing, full historical attempt reconstruction and deeper report validation
remain separate work. Unpublished primary-checkout research remains untouched.
