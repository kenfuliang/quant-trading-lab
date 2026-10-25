---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Leveraged SPY comparisons

- Work status: complete
- Scope: explicitly requested research extension, separate from the original saved-SPY evidence. Canonical owner: [leverage model](../../research/leverage-model.md); operation: [performance SOP](../operations/performance.md).
- Acceptance: defined financing/sizing/margin model, eight base simulations ($300,000; two signals × 1/1.25/1.5/2), overall/yearly return, drawdown, Calmar and Sharpe; browser ranking, ledgers/CSV, separate MLflow experiment; preserve original runs. Financing/margin stress comparisons.
- Failure cases: forward-data isolation, weekend interest, dividend entitlement, initial/maintenance constraints, gap/intraday liquidation, insolvency and halted behavior, repeat imports.
- Validation: `make check` exit 0, 27 tests, dependency check and 39-file docs check. `make leverage-comparison` exit 0 for initial import and cached repeat; 24 reconciled research paths, eight base MLflow runs in experiment 2. Original two runs in experiment 1 preserved. Each daily metric retains exactly 5284 observations per run; summary Calmar and financing have one observation each.
- Financial evidence: [receipt](evidence/2026-10-25-leverage-comparison.json), identity `3aba31cfafe4da76ff123bbf2d9c83bb2a7e29dc181c23b1459776c1ef9a0454`. Independent Decimal audit: 126792 session ledgers, 79448 fills; maximum balance difference 1.26e-8 USD. Independent Decimal validation of all 528 annual/overall score rows, interest totals, ranks and ties. Earlier development result identity 5466ce479e6996d7 retained; the latest pointer identifies the active view.
- Browser evidence: eight base portfolios, year 2020 filter, Sharpe ranking, higher-maintenance stress showing HALTED/N/A verified. Screenshot in `.local/screenshots/leverage-comparison.png`.
- Canonical impact: model document owns financial rules; performance SOP owns operation; docs map, architecture and root capability status updated. No roadmap milestone promoted; generic native execution/margin proof remains planned.
- Limits: fixed illustrative financing; simplified initial/maintenance and OHLC-low liquidation; daily-close score drawdown; no real IBKR/SMA/settlement reconstruction. This separate portfolio-ledger research engine does not configure the Nautilus execution runtime. No broker operation or original result replacement.
- Recovery: completed matching artifacts hash-check before reuse; incomplete result folders retained/fail closed. Repeat import reuses finished runs. Operational backup/restore remains outside this slice.
- Outcome: leverage reduced base-case Calmar/Sharpe as financing and drawdown increased. Two forced liquidations appear in the 50% maintenance stress, none in the base path; absence in base does not establish broker safety.
- Next action: review assumptions and annual/stress comparisons in the browser before considering any execution scope.
