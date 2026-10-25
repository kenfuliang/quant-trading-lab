# SPY leverage and financing model

Status: active research contract v1. Updated 2026-10-25. This file owns financial
assumptions for `research/leveraged_spy.py`. The [performance SOP](../docs/operations/performance.md)
owns operation. This is a deterministic portfolio-ledger simulation, not a
Nautilus execution or IBKR margin validation. Original results remain unchanged.

```text
Frozen SPY OHLC/dividends + prior-close EMA50/200 signal
 → calendar-day interest → prior-holding dividends → opening margin check
 → whole-share sizing/fills → low-price margin check → close valuation
 → independent ledger audit → annual/full-period comparison
```

## Comparable scenarios

USD 300,000 initial equity per portfolio; same frozen 2004–2025 source snapshot,
2004 warm-up and 2005-01-03 through 2025-12-31 evaluation. Signals: EMA50 > EMA200
means long, otherwise cash; always-long is the buy-and-hold **signal** comparator.
Read the signal from the previous completed daily bar, not today's close. Use the
same exponential indicator definition as the saved experiment; saved indicator
states are source fixtures and are checked against the source data/previous dates.

Nominal exposure labels 1x, 1.25x, 1.5x and 2x are research targets, not approved
trading limits. At every session open, target notional is 99% × label × equity
**after** that trade's costs. Choose the maximum whole-share quantity satisfying
that constraint. No shorts. Check 50% initial equity/notional before increasing
shares. Daily sizing automatically redeploys dividend cash and differs from the
original entry-only $100,000 fixture. The 1x cases therefore form new matched
baselines, not exact reproductions or simple scaling of those old portfolios.

Each nonzero trade pays $1 and fills at open × (1 ± 5 basis points), rounded to
cents. Cash and interest are carried at full precision; displayed values round only
for presentation. No market impact, partial fills, settlement lag or taxes. Shares
mark at raw closes. Dividends credit cash on ex-date using previous holdings before
opening trades; payment-date timing and withholding are omitted. Positive cash
interest is zero. No forced final liquidation fee for open holdings.

## Financing

Base fixed debit rate: **6% annual**, purely illustrative for every historical year;
not today's IBKR quote or historical borrowing-rate reconstruction. Before a session
open, subtract `max(-previous_cash,0) × annual_rate × elapsed_calendar_days / 360`.
Interest is charged immediately to cash at that open; the next interval uses that
updated balance. Friday-to-Monday includes three days. No debt before first entry,
no charge beyond final close. This intentionally simplifies settlement balances,
rate tiers and monthly posting. A 9% fixed-rate sensitivity repeats every scenario.

IBKR describes daily interest accrual and monthly posting; its actual rules/rates
are not duplicated here: [interest calculation](https://www.interactivebrokers.com/en/trading/margin-calculation-details.php).

## Margin and stress behavior

Base maintenance is 25% of marked long stock value, initial purchase requirement
50%. These stylized rules do not model SMA, portfolio margin, jurisdiction/account
rules, concentration, broker discretion or real-time execution. IBKR explains the
[Reg T framework](https://portal.interactivebrokers.com/en/trading/margin-education.php).
Separate sensitivity uses 50% maintenance for the whole period (with initial margin
also 50%); base is not mixed with stress when ranking.

Check prior positions at today's opening price **after** interest/dividend credits,
before voluntary trades. After rebalancing, check at the day's low and at close.
If equity < maintenance × notional or equity <= 0, sell all at the checked mark
minus 5 bps and $1, record a forced liquidation, and remain halted/cash for the rest
of the sample. A low-trigger uses the observed low as a conservative fill mark,
not an inferred exact trigger time. OHLC cannot establish fill availability or
real broker liquidation ordering. Reject an initial-margin-violating increase
instead of pretending it executed. This model does not auto-sell at 30% drawdown;
that remains a reassessment reference, not a guaranteed stop.

Negative equity remains a liability: do not floor to zero. Continue debt interest
while halted. Preserve negative/zero balances and mark return-ratio scores after
insolvency as N/A rather than interpreting returns across negative equity.

## Measurement and receipts

Overall CAGR uses the same first-to-last session calendar-duration convention as
the original fixture. Total return is separate. Drawdown includes initial equity;
annual drawdown resets to the previous year-end balance. Calmar = CAGR / absolute
full-period drawdown; annual Calmar = year return / absolute within-year drawdown.
Sharpe = mean daily simple return / sample stdev × sqrt(252), 0% risk-free, excluding
the synthetic anchor. Annual scores use that year's returns including the first
session's return from the prior year-end. No drawdown/variance means N/A. Post-
insolvency ratios are N/A; the dashboard still displays loss/drawdown and status.

Daily financing, commissions, dividend credits, market value, exposure, maintenance
buffer and trade/forced-liquidation events are preserved. Maximum modeled exposure
and minimum maintenance buffer use checked open/low/close marks; the buffer is
`(equity − maintenance_requirement) / equity × 100` when equity is positive.
No position means zero margin use and a 100% buffer. Annual costs aggregate dates;
all scores use net portfolio equity rather than return on posted margin.

Each immutable report run records input/code/config hashes and independent ledger
reconciliation. Stress ledgers and summaries are retained alongside base cases.
No broker access or orders are needed. This research cannot establish actual
account eligibility, liquidation safety or future achievement of return targets.
