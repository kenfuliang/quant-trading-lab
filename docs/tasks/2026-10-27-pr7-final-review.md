---
status: active
updated: 2026-10-27
owner: project-maintainers
---

# PR #7 final review and merge verification

Work status: fixes re-reviewed; final offline checks passed; exact-head hosted CI required before merge.
Review base `4fc663164434e15b68324d8266ff421294af717b`, initial PR head
`7d7612252094bf32790afc0ef559a681ea48dbdc`. Requirements are the
[bounded integration task](2026-10-27-rsi-integration.md); canonical operation is
in the [RSI SOP](../operations/recursive-research.md). This user-authorized review
and merge task is separate from the closed integration verification budget.
It authorizes offline regression checks, not a second demo, financial launch or
reopening historical studies. No historical receipt or raw bundle is rewritten.

## Requirements findings

Two P2 issues were reproduced with disposable synthetic registry state:

- Losing both journal and head could silently initialize a replacement registry,
  resetting an adopted incumbent without an explicit rollback record.
- Losing or replacing the lock could admit a second writer on a different inode.

The initialization marker now persists before the first journal append and binds
configuration and local lock identity. Missing journal/head on an initialized
registry, including an active writer, fails without replacement authority. A
missing initialized lock fails before a substitute is created; a replaced lock
fails persistent and active checks. Repeated reopen attempts cannot reset either
state or writer admission. Both requirements findings were rechecked as resolved.

## Standards findings

Standards review also found missing-authority acceptance and confirmed a FIFO
journal blocked on a content read. Lock, journal, head and marker now require
regular non-symlink files; reads use nonblocking/no-follow descriptors. The writer
retains an authority seal and verifies lock device/inode before loading, appending
and sealing state. FIFO tests run in bounded disposable subprocesses; symlink
regressions preserve the outside target. The final standards re-review found no
remaining actionable finding and independently passed all 29 adoption tests.

## Verification and preservation

Nine new regression methods cover adopted-authority loss, active loss, valid older
authority, unmarked/partial initialization, FIFO inputs, symlinks, missing lock and
replaced lock with repeated reopen attempts. They add no financial simulation.
Full checks and exact published-head CI are recorded in the
[review receipt](evidence/2026-10-27-pr7-final-review.json) and PR handoff.
Original 449-test and 502-test receipts and the single 25-artifact demo remain
historical evidence; this review does not regenerate or overwrite them.

The source fix changes the registry's current initialization contract. Unmarked
prior histories and copied/moved lock identities require separately reviewed
reconciliation. Automatic marker creation for existing histories is intentionally
unsupported. This cannot establish offsite portability, evaluator independence,
financial alpha or broker readiness. Failed synthetic reproductions are retained
in the dated review area, not disguised as successful financial results.

## Merge gate and next eligible work

Before merge: verify protected/source evidence unchanged, current tests and docs,
exact-head hosted CI, live base/head and absence of review objections. Merge is
SHA guarded; post-merge main CI is checked separately. The primary dirty checkout
remains untouched. A completed engineering task does not adopt a financial version.

The next proposed goal is a broader known-lesson corpus with independent rejection
fixtures and equal-budget comparison against a simple checklist. It would use saved
or synthetic evidence only, no new financial runs, and preserve ties/failures.
This review recommends that direction; it does not start a new goal or evaluator.


## Final offline verification

`make check` passed all **511 tests**, documentation/metadata checks for 99 files,
boundary checks for 64 modules and index coverage for 14 entries/12 published plans.
Both review tracks rechecked all three unique issues: requirements two findings
resolved, standards two initial findings resolved plus the related lock guard
rechecked; zero remaining blockers. The standards reviewer independently ran all
29 adoption tests. Existing 405 protected shared-main files, 13 primary foundation
inputs, 296 primary historical inputs and all 25 original demo artifacts match
their pinned hashes. No new demo, real saved preflight or financial launch occurred.
