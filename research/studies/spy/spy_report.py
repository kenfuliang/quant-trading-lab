"""Durable CSV, JSON, Markdown and scientific-chart outputs for the SPY run."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter, PercentFormatter
import numpy as np
import pandas as pd

from .spy_backtest import INITIAL_CASH

LABELS = {"trend": "EMA 50/200", "buy_hold": "Buy & hold"}


def annual_returns(curve):
    end = curve.equity.groupby(pd.to_datetime(curve.index).year).last()
    previous = end.shift(1)
    previous.iloc[0] = INITIAL_CASH
    return (end / previous - 1) * 100


def plot_comparison(runs, output):
    # Chart contract: compare 5,283 daily portfolio values and EOD drawdowns.
    # Scientific PNG/SVG artifact; line panels are appropriate for both time
    # series. One blue root for trend, charcoal dashed benchmark, same data as CSV.
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "text.parse_math": False,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": "#30343B", "text.color": "#30343B"})
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1]}, layout="constrained")
    styles = {"trend": ("#2878B5", "-"), "buy_hold": ("#42464D", "--")}
    for mode, run in runs.items():
        curve = run["curve"]
        dates = pd.DatetimeIndex([pd.Timestamp(curve.index[0]) - pd.Timedelta(days=1), *pd.to_datetime(curve.index)])
        values = np.r_[INITIAL_CASH, curve.equity.to_numpy()]
        dd = values / np.maximum.accumulate(values) - 1
        color, style = styles[mode]
        axes[0].plot(dates, values, color=color, linestyle=style, linewidth=1.7,
                     label=f'{LABELS[mode]} · ${values[-1]:,.0f}')
        axes[1].plot(dates, dd, color=color, linestyle=style, linewidth=1.4)
    for ax in axes:
        ax.grid(axis="y", color="#E5E7EB", linewidth=.65)
        ax.spines["left"].set_color("#A8ADB4")
        ax.spines["bottom"].set_color("#A8ADB4")
    axes[0].set_ylim(bottom=0)
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda n, _: f"${n / 1000:,.0f}k"))
    axes[0].set_ylabel("Portfolio value (USD)")
    axes[0].legend(loc="upper left", frameon=False)
    axes[1].yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    axes[1].set_ylabel("Drawdown\nfrom prior peak")
    axes[1].set_ylim(-.60, .02)
    axes[1].set_xlabel("Session date")
    axes[1].xaxis.set_major_locator(mdates.YearLocator(5))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    first_curve = next(iter(runs.values()))["curve"]
    axes[1].set_xlim(pd.Timestamp(first_curve.index[0]).replace(month=1, day=1), pd.Timestamp(first_curve.index[-1]) + pd.Timedelta(days=20))
    fig.suptitle("SPY: more growth from holding, smaller drawdowns with the EMA rule", x=.055, ha="left", fontsize=15, fontweight="bold")
    axes[0].set_title("2005–2025 · $100,000 start · daily observations · 5 bps per side + $1 per order", loc="left", fontsize=10, pad=12)
    fig.supxlabel("Source: Yahoo daily OHLC + cash dividends; NautilusTrader simulation. No automatic dividend reinvestment.\nDividends credited on ex-date; cash earns 0%. Open positions marked to final close; no exit fee charged.", fontsize=9)
    fig.savefig(output / "comparison.png", dpi=160)
    fig.savefig(output / "comparison.svg")
    plt.close(fig)


def write_report(runs, manifest, output):
    summaries = {mode: run["metrics"] for mode, run in runs.items()}
    (output / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    pd.DataFrame(summaries).T.to_csv(output / "metrics.csv", index_label="portfolio")
    annual = pd.DataFrame({LABELS[m]: annual_returns(r["curve"]) for m, r in runs.items()})
    annual.index.name = "year"
    annual.to_csv(output / "annual_returns.csv")
    chart_data = []
    for mode, run in runs.items():
        run["curve"].to_csv(output / f"{mode}_equity.csv")
        run["fills"].to_csv(output / f"{mode}_fills.csv")
        run["credits"].to_csv(output / f"{mode}_dividends.csv", index=False)
        run["orders"].to_csv(output / f"{mode}_orders.csv")
        expanded = run["curve"].copy()
        expanded["portfolio"] = LABELS[mode]
        expanded["initial_cash"] = INITIAL_CASH
        expanded["drawdown_pct"] = (expanded.equity / expanded.equity.cummax().clip(lower=INITIAL_CASH) - 1) * 100
        chart_data.append(expanded)
    pd.concat(chart_data).to_csv(output / "chart_data.csv")
    plot_comparison(runs, output)
    a, b = summaries["trend"], summaries["buy_hold"]
    rows = [
        ("Ending portfolio value", f'${a["ending_equity"]:,.2f}', f'${b["ending_equity"]:,.2f}'),
        ("Total return", f'{a["total_return_pct"]:.2f}%', f'{b["total_return_pct"]:.2f}%'),
        ("Annualized compound return", f'{a["cagr_pct"]:.2f}%', f'{b["cagr_pct"]:.2f}%'),
        ("Maximum daily-close drawdown", f'{a["max_drawdown_pct"]:.2f}%', f'{b["max_drawdown_pct"]:.2f}%'),
        ("Annualized daily volatility", f'{a["annualized_volatility_pct"]:.2f}%', f'{b["annualized_volatility_pct"]:.2f}%'),
        ("Sharpe (0% risk-free assumption)", f'{a["sharpe_zero_rf"]:.2f}', f'{b["sharpe_zero_rf"]:.2f}'),
        ("Sessions holding SPY", f'{a["exposure_days_pct"]:.2f}%', f'{b["exposure_days_pct"]:.2f}%'),
        ("Filled orders", str(a["filled_orders"]), str(b["filled_orders"])),
        ("Cash dividends credited", f'${a["dividend_cash"]:,.2f}', f'${b["dividend_cash"]:,.2f}'),
        ("Commission paid", f'${a["commission_usd"]:,.2f}', f'${b["commission_usd"]:,.2f}'),
        ("Modeled spread/slippage cost", f'${a["modeled_spread_slippage_usd"]:,.2f}', f'${b["modeled_spread_slippage_usd"]:,.2f}'),
    ]
    table = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    report = f'''# SPY: EMA 50/200 versus buy-and-hold

Status: completed historical simulation, independently reconciled. Generated {manifest["created_local"]}.
Methodology owner: [research/README.md](../../../research/README.md).

Buy-and-hold finished **${b["ending_equity"] - a["ending_equity"]:,.0f} ahead**. The EMA rule reduced the largest daily-close decline from {abs(b["max_drawdown_pct"]):.1f}% to {abs(a["max_drawdown_pct"]):.1f}%. This one fixed-rule historical comparison does not establish a durable trading edge.

![Portfolio value and daily-close drawdowns](comparison.png)

| Measure | EMA 50/200 | Buy & hold, cash dividends |
|---|---:|---:|
{table}

## Experiment

- SPY daily data: {runs["trend"]["curve"].index[0]} through {runs["trend"]["curve"].index[-1]}, {a["sessions"]:,} sessions. Calendar 2004 is indicator warm-up only.
- Starting cash: $100,000 each; whole shares; cash account; no shorting or borrowing.
- EMA rule: after each daily close, hold SPY when EMA(50) > EMA(200), otherwise cash. Changes execute at the **next session open**. The first signal uses completed 2004 history.
- Each entry allocates approximately 99% of available cash. No continuous rebalancing. Buy-and-hold buys at the first tested open and retains the shares.
- $1 commission per filled order and 5 basis points of combined half-spread/slippage per side, rounded to the cent. These are illustrative assumptions, not an IBKR pricing quote. Cost is embedded in synthetic bid/ask quotes; the augmented fill CSV records it separately.
- Dividends are credited to cash on ex-date based on the prior session's holdings. They are **not automatically reinvested**. The EMA rule can redeploy accumulated cash on a later entry; buy-and-hold retains its dividends in cash.
- End values mark any open shares to the last close; neither portfolio is forced to sell. Exit costs for those final holdings are not charged. Cash interest and taxes are zero.

## Checks

All {a["sessions"]:,} daily balances in each portfolio and all {a["filled_orders"] + b["filled_orders"]} fills match a separate pandas/Decimal ledger within five cents. Audit details and the raw-data SHA-256 are in [manifest.json](manifest.json). Checks cover prior-close signals, next-open prices, sizing, dividend entitlement, fees, and cash borrowing. Behavior tests also verify that changing future data cannot alter earlier results.

## Interpretation limits

This is one historical period and one manually selected rule, with no parameter search and no independent holdout claim. The daily OHLC feed comes from Yahoo Finance and has not been independently reconciled against an exchange feed. Raw closes drive the signal; Yahoo adjusted close is not used. No splits occur in this snapshot; the loader rejects snapshots with splits.

The simulator uses synthetic open/close quotes, not observed bid/ask history. It assumes complete fills, ample liquidity, immediate settlement, and generic 09:30/16:00 New York event times; early-close sessions are not modeled intraday. Drawdowns use daily closes and can understate intraday losses. Dividends are made available before their actual payment dates. The buy-and-hold benchmark is not a dividend-reinvestment total-return index. None of these results verifies an IBKR connection or future execution quality.

## Reproduce and inspect

From the workspace root:

```sh
.venv/bin/python scripts/current/spy_backtest.py --data {manifest["source_snapshot_relative"]}
.venv/bin/python -m unittest discover -s tests -v
```

Each run writes a new folder. The frozen [source snapshot](source-data.json), normalized [daily inputs](input_daily.csv), per-portfolio equity/fill/dividend files, [annual returns](annual_returns.csv), and [chart source data](chart_data.csv) are retained together. Reproduction does not refresh or replace the snapshot.
'''
    (output / "report.md").write_text(report)
