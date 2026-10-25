---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Independent review of bounded research accounting and recovery

Work status: completed scoped review and wrapper mitigation. This is a task receipt,
not a new accounting-method owner. [Research scoring](../research-scoring.md),
[research development](../research-development.md), the
[program](2026-10-25-recursive-research-program.md) and
[pilot](2026-10-25-recursive-research-pilot.md) retain their responsibilities.

Reviewed `research/research_controller.py`, `research/bounded_study.py`, their
existing tests, scoring contracts and frozen pilot scope. Fresh probes used
handcrafted two-session account data, temporary journals and mocked synthetic
execution. No new historical financial study, network request, install, broker
operation or change to historical evidence was performed by this review lane.
Coordinator owns any later actual pilot simulation attempts.

```text
Original audit boundary
  synthetic ledger with NaN or extra row → incorrectly reports passed

New bounded-study boundary
  exact session/schema/finite-state checks → Decimal replay → metrics/artifacts
           ↑                                      ↑
  checked again on cache reuse          prior inputs checked before/after
```

## Findings and actual before/after results

| Priority | Fresh finding | Before observation | Disposition |
| --- | --- | --- | --- |
| P1 | Legacy `leverage_audit.reconcile` does not reject nonfinite observed cash/equity | A handcrafted all-cash ledger with final cash and equity NaN returned `passed=True`, two sessions, zero fills and maximum difference0 | New bounded-study validation rejects nonfinite account/trade fields before replay/scoring and during cache reuse; fresh regression passes |
| P1 | Replay loops over input sessions but does not reject extra output sessions | A two-session input plus a third unaudited equity row of USD9999999 returned `passed=True`, sessions3 | New wrapper requires output index exactly equal to declared signal sessions; extra, missing, duplicate or reordered output dates reject |
| P2 | Controller preview inherited `state=ready` after its attempt budget stopped selection | With max_attempts1, a second-question preview returned ready, selected null, and an explicit exhaustion reason | Reported to coordinator/controller author for correction; reservation itself was already blocked. This review does not claim its later fix was independently retested here |

The NaN defect follows from a difference comparison where `NaN > tolerance` is
false. The extra-date defect matters because later metrics use the whole output
curve, not just dates inspected by the legacy audit. Neither finding establishes
that preserved historical results contain either corruption.

## Implemented mitigation and verification

Changed [bounded study](../../research/bounded_study.py) adds
`validate_financial_outputs(frame, curve, trades)` before the existing audit and
on completed-cache reuse. It checks exact output coverage, required account
fields, finite numeric values, explicit boolean flags, integer holdings/counts,
trade-field schema, finite positive trade prices, integer trade quantities and
trade dates within the input sessions. Cache reuse also verifies signal session
coverage, audit session/fill counts and finite maximum-difference bounds in addition
to the already implemented artifact hash checks. Matching a corrupted file's
rewritten manifest checksum cannot bypass these semantic guards.

The new [adversarial tests](../../tests/test_bounded_study_adversarial.py) exercised:

- NaN/infinity in cash, equity, holdings, financing, dividends and margin buffer;
  nonnumeric numeric fields, malformed boolean flags and fractional shares.
- Extra/missing/duplicated/reordered ledger dates; extra trade dates and nonfinite
  trade cash; correctly accepted finite all-cash output with no trades.
- Mocked wrapper output corruption: rejection occurs before Decimal replay and a
  failed manifest retains the partial signal artifact.
- A synthetically completed cache then corrupted cash with matching updated file
  checksum: semantic revalidation still rejects reuse.
- A same-day raw-price perturbation: the already lagged mixture allocation target
  is unchanged through that same session. This checks that wrapping introduces no
  same-day leak; it is not a comprehensive proof of every signal implementation.

Actual commands/results:

- `.venv/bin/python -m unittest discover -s tests -p test_bounded_study.py -v`:
  nine existing wrapper tests passed, exit0.
- `.venv/bin/python -m unittest discover -s tests -p test_bounded_study_adversarial.py -v`:
  eight fresh tests passed, exit0.
- Combined discovery with `-p 'test_bounded_study*.py'`:17 tests passed, exit0.
- Read-only scan of all88 original suite ledgers at
  `reports/strategy-suite/97fc0717512bee9e`:464904 rows; no nonfinite values in
  numeric ledger columns. This lane checked numeric finiteness, not independent
  artifact identity or every accounting/trade field; prior audit receipts retain
  their own scope.

## Input identity and retained limitations

The wrapper changed before any actual pilot simulation attempts according to the
coordinator; the earlier preflight-only plan must be superseded and freshly pinned
before execution. Stable wrapper SHA256 after mitigation is
`9a6165423a8dfcff9c96acb1d8c0d8a31d7d037617f72c8d70b81b78042a09d0`.
The [machine-readable review](evidence/2026-10-25-recursive-research-adversarial-review.json)
records source/test identities, probe outcomes and observed checks.

**Legacy core audit remains vulnerable if called directly.** It was deliberately
not modified in this task so old study input identities/evidence remain unchanged.
Any new direct caller must obtain an equivalent guard or a separately versioned
core repair first. Existing ledger finiteness is reassuring within that narrow
check; it does not fix the legacy implementation or prove all saved fields.

The bounded runner's per-plan max_cases is not a global program budget. The
coordinator must reserve global financial attempts before launch and retain
failures. Controller logical-action/resource accounting does not meter actual
processes, verify evidence content or execute a study. Caller-supplied resolutions
remain claims until independent evidence review. The journal's locks/hash chain
support local recovery, not resistance to an adversary rewriting both journal and
snapshot. Exact observation equality cannot infer all semantic duplicates.

This review did not claim continuous crash/power-loss durability, a full filesystem
security audit, native/broker parity or financial effectiveness. Root's final
regression/integration checks and actual pilot evidence remain separate.
