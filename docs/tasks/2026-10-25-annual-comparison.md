---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Annual saved-SPY comparison

- Work status: complete
- Scope: M2 saved-result extension; [performance SOP](../operations/performance.md) owns operation and metric definitions. No strategy rerun or broker use.
- Acceptance: common 2005–2025 yearly table, return and within-year daily-close drawdown charts, CSV download and MLflow artifacts; preserve the two existing runs and raw source evidence.
- Definitions: year-end / previous year-end minus one; first year uses initial cash. Drawdown resets to previous year-end equity, then uses daily closes within the year.
- Failure cases: unmatched dates rejected by saved-run loader; tests cover year boundary, first-day losses, continuing drawdown reset, zero-loss years and compounded return reconciliation.
- Inputs before edits: saved_runs.py SHA256 bdeeda2b76757137b5a1a0961ea2f3fc5cc62cd9bd3dd9ac437957e7e472e21d; test_saved_reports.py d75c5fb3406aba49fb027a337760c47c99f773744bdccf9b322f41654db3f15b. Git has no baseline commit; unrelated files preserved.
- Validation: `make performance` exit 0 refreshed artifacts on the same two FINISHED MLflow run IDs; `make check` exit 0 (12 tests, dependency check and 37-file documentation check). Independent Decimal calculation verified all 42 strategy-year rows against original equity CSVs and compounded annual returns reconciled to final balances within 1e-10.
- Browser: observed both charts and all 21 annual rows at `http://127.0.0.1:8765/ab5184b062404373/annual-comparison.html`; CSV available alongside it. Existing summary/history definitions preserved.
- Canonical impact: performance SOP owns annual formulas/navigation; root README updated availability. M2 remains partial; no roadmap milestone promoted.
- Limitations: daily-close drawdown only, annual peak resets, fixed SPY fixture; generic partial-year ingestion remains planned. No full SPY backtest or broker operation performed; regression tests use small synthetic strategy fixtures.
- Next action: use annual view to inspect years; infrastructure roadmap priority remains M1.
