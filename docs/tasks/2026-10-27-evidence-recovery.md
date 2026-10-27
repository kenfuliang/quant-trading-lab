---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# Closed research evidence recovery drill

Work status: real-bundle drill and full offline verification passed; hosted CI follows publication.
PR #6 parent `d36b3b134260cb14bd9a9f9a119d4b59caa05b58`.
[Recovery SOP](../operations/evidence-recovery.md) owns commands and limits;
[receipt](evidence/2026-10-27-evidence-recovery.json) records hashes and findings.
This supports an M3 file-bundle proof only; roadmap status is unchanged.

## Scope and acceptance

Restore one completed and one failed historical research bundle from separately
verified recovery copies outside the checkout into new disposable folders. Compare
every restored file to the original before/after inventory and to saved artifact
hashes. Preserve original manifests, failure JSON, stopped status, deadlines,
plans and trial budgets. No financial rerun, broker operation or worker resumption.
Publish redacted aggregate/hash evidence only; raw copies remain private.

The implementation must reject corrupt/unlisted/missing files, unsupported active
statuses, unsafe paths, symlinks, overlaps, wrong pinned inventory hashes and any
existing destination. Interrupted operations preserve partial output and reject
reuse; synthetic tests cover those failures through the actual CLI. Run full CI.

## Actual drill

| Bundle | Original saved status | Files restored | Saved artifact hashes checked |
| --- | --- | ---: | ---: |
| Cost-stress `5486c626…` | completed | 23 | 22 |
| Risk-gate recovery `97e9d442…` | recovery_failed_no_further_launch | 15 | 14 |

Both restored bundles match all original bytes, including the two saved manifests.
The failed bundle's failure JSON and terminal status are unchanged. Originals and
recovery copies remained unchanged before/after. Full identities, SHA-256 values
and raw local storage pointers are retained privately; the public receipt includes
source bundle identities and the separately pinned inventory hashes.

An initial drill passed; after adding explicit rejection of nonterminal statuses,
the same originals were copied/restored again with the final implementation. Both
run directories and their original receipts remain preserved outside the checkout.
No attempt was a financial simulation or a retry of the historical failed study.

## Offline validation

`make check` passed 422 tests, documentation checks for 95 files, the boundary gate
for 59 modules and the generated evidence-index gate. All 405 pre-existing
protected/research evidence files checked remain unchanged, including all 327
frozen files and the compatibility manifest. The index was regenerated only to
include this new supporting task/receipt; prior study associations remain unchanged.

## Rescore

The prior rubric/weights are retained. Recovery/portability moves **5 → 7/10** for
this concrete closed-file proof. Other dimensions receive no increase. The weighted
structure assessment moves **8.1 → 8.2/10** (rounded); it is engineering judgment,
not financial quality or general disaster-recovery certification.

| Perspective | Weight | Before | After |
| --- | --- | --- | --- |
| Responsibility and ownership | 15% | 8.5 | 8.5 |
| Dependency boundaries | 15% | 8.5 | 8.5 |
| Discoverability and onboarding | 10% | 8 | 8 |
| Frozen evidence preservation | 15% | 9 | 9 |
| Single source of truth | 10% | 8 | 8 |
| Content and report structure | 10% | 8.5 | 8.5 |
| Automated structural checks | 10% | 8.5 | 8.5 |
| Growth across research families | 10% | 6 | 6 |
| Evidence recovery and portability | 5% | 5 | 7 |

## Lesson and next evidence

A failed bundle must restore as failed; successful copying never grants a retry or
changes a study result. A separately retained inventory hash distinguishes a
verified recovery copy from a convenient folder copy. Same-machine copies cannot
prove loss-of-machine survival. A separately scoped next recovery test would need
independent storage and consistent database/artifact capture, with a full dependency
closure where financial replay is intended. No such readiness is claimed here.

Rollback removes this additive tool, tests and SOP/navigation changes; preserve
all originals, recovery copies and disposable drill receipts. No data-store migration
or external-state rollback is required.
