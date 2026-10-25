---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Saved strategy score ranking

- Work status: complete
- Scope: M2 saved-SPY comparison extension. Canonical owner: [performance SOP](../operations/performance.md).
- Acceptance: full-period and annual Calmar/Sharpe, period/score selectors and ranked strategy rows, annual score charts/CSV and MLflow report artifacts; additive overall Calmar metric; preserve existing runs and daily histories.
- Definitions: overall CAGR / absolute full-period drawdown; annual return / absolute within-year drawdown; annualized daily Sharpe at 0% risk-free with sample standard deviation and 252 sessions. Exclude synthetic anchor from returns.
- Failure cases: zero drawdown or zero/insufficient daily variance produces N/A and no rank; negative scores rank numerically descending; equal scores share rank; repeat import must not duplicate metrics.
- Pre-edit SHA256: annual.py 0b36d021d3f24b737195dccfaa926293b0d91b89b960737aa86bf5e2c7391a28; saved_runs.py 8ca37c8b5ff0f9aaa1f42ad769bb289c4cecd1d91fe59c3eb9e3dc18ced57f49; import_performance_mlflow.py 0cd730000ec64697df81887b7e9fb887bdc4d4517228a751ed9697482c7d7a9a; test_annual_reports.py c5c122a4f2bcd2a361e94bc2196c01fd4d5b050ca6609ebda11dc82cac3427f3. Git has no baseline commit; unrelated work preserved.
- Validation: `make check` exit 0: 17 tests, dependency check and 38-file docs check. `make performance` exit 0 on repeated refresh; same two FINISHED MLflow runs, one full-period Calmar observation and 5284 observations for each daily metric per run. Score artifact refreshed on both runs.
- Independent evidence: [score validation receipt](evidence/2026-10-25-score-ranking.json) records UTC verification and implementation hashes. Decimal calculations from original daily balances match all 42 annual Calmar/Sharpe results; overall Sharpe matches the audited summary; ranks verified for all 44 period/strategy rows.
- Browser evidence: full-period leaderboard, 2020 period filtering and Sharpe selection visibly verified. Local screenshot: `.local/screenshots/strategy-score-ranking.png`.
- Canonical docs: performance SOP defines formulas, tie/N/A policy and navigation; root README updates capability status. Roadmap M2 remains partial, with M1 still next priority.
- Limits: fixed saved-SPY fixture, daily-close drawdown, 0% risk-free convention, no out-of-sample claim. Negative-score rank can favor a larger loss; dashboard keeps return/drawdown visible and explains this. No strategy tuning, full historical rerun or broker operation.
- Next action: open the comparison dashboard and select a period/score; generic strategy import remains planned.
