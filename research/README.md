# SPY backtest methodology

Status: active local research experiment. Updated 2026-10-24.
This file owns the experiment rules. Root README owns workspace setup; each
immutable run's report and manifest own its observed results.

```text
Frozen Yahoo OHLC/dividend snapshot
              ↓ validation + 2004 warm-up
Prior-close EMA50/200 target ──→ next-open synthetic quotes ──→ Nautilus fills
Buy-and-hold target ──────────→ same simulated venue/costs ───→ Nautilus fills
              ↓
Independent pandas/Decimal ledger → metrics + CSV evidence + PNG/SVG chart
```

The default period is 2005-01-01 through 2025-12-31. The raw daily history begins
2004-01-02 and ends 2025-12-31. Do not silently change windows or parameters after
viewing outcomes; a new hypothesis must be labeled as a new experiment.

Both portfolios begin with $100,000 in a cash account. The EMA rule evaluates
raw close prices only when each daily bar has completed. EMA50 > EMA200 means
long; otherwise flat. Changes execute at next session's open. Each entry uses
99% of cash, minus a $1 order-fee reserve, rounded down to whole shares. A buy
and hold portfolio enters once at the same initial open and keeps its shares.

Synthetic bid/ask quotes apply 5 basis points of combined spread and slippage
on each side of the opening price, rounded to cents; fixed commission is $1
per order. These are illustrative costs, not broker-specific pricing. Daily
bars do not drive simulated fills (`bar_execution=False`). Dividends are
credited to cash at ex-date before opening orders based on previous holdings.
No automatic dividend reinvestment occurs; the EMA rule redeploys available
cash at its next entry, whereas buy-and-hold keeps dividend cash. Open holdings
are marked to the final close without forced liquidation or an exit fee.

CAGR uses actual calendar duration. Volatility and Sharpe use daily returns and
252 sessions/year; Sharpe assumes a 0% risk-free rate. Daily drawdown includes
the initial $100,000 baseline. Cash earns zero interest. No taxes, settlement
lag, partial fills, borrow, or early-close intraday timing are modeled.

Each run preserves input bytes and SHA-256, normalized daily inputs, trade and
dividend ledgers, daily account paths, annual returns, metrics, audit results,
code hashes, and charts in a fresh reports/spy folder. The independent ledger
checks the engine's economic outputs, not its own order IDs or random run IDs.

Chart contract: standalone scientific PNG/SVG for the full daily comparison.
Portfolio-value and daily-drawdown lines answer growth and loss-depth questions.
Use blue solid for the EMA rule and neutral dashed for buy-and-hold, with a
shared time axis, explicit USD/percent units, labeled costs and dividend policy.
Inspect the exported image before delivery. No parameter sweeps are included.

Data limitations: Yahoo retail daily data, not exchange-certified; prices are
rounded to cents, adjusted-close fields unused, no splits supported, ex-date
cash credit substitutes for payment-date timing. Validate other data sources
and a later chronological test before drawing an investment conclusion.

Run from the workspace root:

```sh
.venv/bin/python scripts/spy_backtest.py --download
.venv/bin/python -m unittest discover -s tests -v
```

The download flag fetches only a missing input; it never refreshes an existing
snapshot. Reproduce an existing run with `--data reports/spy/<run>/source-data.json`.
The engine needs no broker login or network connection for a saved-data run.

API reference: matching upstream tag v1.231.0, especially
examples/backtest/databento_ema_cross_long_only_spy_trades.py. Our strategy and
execution assumptions are implemented separately rather than copying that
example's trade size, data subscription, or bar timing.
