#!/usr/bin/env python3
"""Profile one or more daily equity paths through time as a self-contained local page.

Uses reporting.temporal and reporting.annual (the repo's own diagnostics) and draws
inline SVG, so nothing is installed or fetched. Offline and read-only.

  --series NAME=PATH      close-path JSON list of {session, nav_usd}; the first row is the anchor
  --benchmark-csv PATH    optional CSV with date,equity (rebased to the anchor)
  --out PATH              default .local/progress/profile.html (ignored; may hold private results)

Descriptive history only: viewed development data, not a forecast or a risk bound.
"""
import argparse
import html
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reporting.annual import annual_metrics, sharpe
from reporting.temporal import analyze_temporal

TOLERANCE = 0.30
COLORS = ("#1f8a4c", "#2457d6", "#8a8f98", "#c98a00")


def load_path(path):
    rows = json.loads(Path(path).read_text())
    index = pd.to_datetime([r["session"] for r in rows])
    return pd.Series([float(r["nav_usd"]) for r in rows], index=index, name="equity_usd")


def load_benchmark(path, start, end, capital):
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")["equity"].astype(float)
    frame = frame.loc[start:end]
    frame = frame / frame.iloc[0] * capital
    frame.iloc[0] = capital
    return frame.rename("equity_usd")


def analyze(equity):
    capital = float(equity.iloc[0])
    summary, table = analyze_temporal(equity, initial_capital=capital)
    days = (equity.index[-1] - equity.index[0]).days
    cagr = (equity.iloc[-1] / capital) ** (365.25 / days) - 1
    daily = equity.pct_change().iloc[1:]
    annual = annual_metrics(equity.to_frame())
    episodes = sorted(summary["drawdown_episodes"], key=lambda e: e["drawdown"])[:5]
    return {"summary": summary, "table": table, "cagr": cagr, "sharpe": sharpe(daily), "annual": annual,
            "episodes": episodes, "underwater_share": float((table["drawdown"] < 0).mean()), "capital": capital}


def esc(value):
    return html.escape(str(value))


def pct(value, digits=1):
    return "n/a" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value * 100:.{digits}f}%"


def chart(title, note, series, *, log=False, zero=None, band=None, fmt=pct, height=250, width=980, cap_top=None):
    left, right, top, bottom = 56, 10, 10, 24
    dates = sorted(set().union(*[s["values"].dropna().index for s in series]))
    if not dates:
        return ""
    x0, x1 = dates[0].value, dates[-1].value
    values = [v for s in series for v in s["values"].dropna()]
    if log:
        values = [math.log10(v) for v in values]
    low, high = min(values + ([zero] if zero is not None and not log else [])), max(values + ([zero] if zero is not None and not log else []))
    if band is not None:
        low = min(low, band)
    pad = (high - low) * 0.06 or 1
    low, high = low - pad, (cap_top if cap_top is not None else high + pad)

    def px(date):
        return left + (date.value - x0) / (x1 - x0 or 1) * (width - left - right)

    def py(v):
        v = math.log10(v) if log else v
        return top + (high - v) / (high - low) * (height - top - bottom)

    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">']
    for i in range(5):
        v = low + (high - low) * i / 4
        y = top + (high - v) / (high - low) * (height - top - bottom)
        shown = 10 ** v if log else v
        label = f"${shown:,.0f}" if log else fmt(shown, 0)
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" class="axis">{esc(label)}</text>')
    for year in range(dates[0].year, dates[-1].year + 2):
        stamp = pd.Timestamp(year=year, month=1, day=1)
        if dates[0] - pd.Timedelta(days=7) <= stamp <= dates[-1]:
            out.append(f'<text x="{px(stamp):.1f}" y="{height - 6}" text-anchor="middle" class="axis">{year}</text>')
    if zero is not None and not log:
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{py(zero):.1f}" y2="{py(zero):.1f}" class="zero"/>')
    if band is not None:
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{py(band):.1f}" y2="{py(band):.1f}" class="band"/>'
                   f'<text x="{width - right - 4}" y="{py(band) - 4:.1f}" text-anchor="end" class="axis">30% tolerance</text>')
    for s in series:
        points = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in s["values"].dropna().items())
        out.append(f'<polyline points="{points}" fill="none" stroke="{s["color"]}" stroke-width="1.6" stroke-linejoin="round"/>')
    out.append("</svg>")
    legend = "".join(f'<span><i style="background:{s["color"]}"></i>{esc(s["name"])}</span>' for s in series)
    return f'<section class="card"><h2>{esc(title)}</h2><p class="n">{esc(note)}</p>{"".join(out)}<div class="legend">{legend}</div></section>'


def render(results, names):
    colors = dict(zip(names, COLORS))

    def line(key, **kw):
        return [{"name": n, "color": colors[n], "values": key(results[n])} for n in names]

    summary_rows = []
    for label, get in [
        ("Ending equity", lambda r: f"${r['table']['equity_usd'].iloc[-1]:,.0f}"),
        ("Net CAGR", lambda r: pct(r["cagr"])),
        ("Max drawdown", lambda r: pct(-r["summary"]["max_drawdown"])),
        ("Calmar (CAGR / max DD)", lambda r: f"{r['cagr'] / -r['summary']['max_drawdown']:.2f}"),
        ("Sharpe (zero risk-free)", lambda r: "n/a" if r["sharpe"] is None else f"{r['sharpe']:.2f}"),
        ("Longest underwater (sessions / days)", lambda r: f"{r['summary']['longest_underwater_duration_sessions']} / {r['summary']['longest_underwater_duration_calendar_days']}"),
        ("Share of sessions below a prior peak", lambda r: pct(r["underwater_share"], 0)),
        ("Worst 21-session return", lambda r: pct(r["summary"]["worst_returns"]["21"]["return"])),
        ("Worst 63-session return", lambda r: pct(r["summary"]["worst_returns"]["63"]["return"])),
        ("Daily ES95 loss", lambda r: pct(r["summary"]["historical_daily_es95"]["loss_magnitude"], 2)),
        ("Drawdown beyond 30% tolerance", lambda r: "yes" if -r["summary"]["max_drawdown"] > TOLERANCE else "no"),
    ]:
        summary_rows.append("<tr><th>" + esc(label) + "</th>" + "".join(f"<td>{esc(get(results[n]))}</td>" for n in names) + "</tr>")
    head = "<tr><th></th>" + "".join(f'<th><i style="background:{colors[n]}" class="dot"></i>{esc(n)}</th>' for n in names) + "</tr>"

    years = sorted(set().union(*[set(results[n]["annual"].year) for n in names]))
    annual = ["<tr><th>Year</th>" + "".join(f"<th>{esc(n)} return</th><th>{esc(n)} max DD</th>" for n in names) + "</tr>"]
    for year in years:
        cells = []
        for n in names:
            row = results[n]["annual"][results[n]["annual"].year == year]
            cells.append("<td>" + (pct(row.annual_return_pct.iloc[0] / 100) if len(row) else "n/a") + "</td><td>" +
                         (pct(row.annual_max_drawdown_pct.iloc[0] / 100) if len(row) else "n/a") + "</td>")
        annual.append(f"<tr><th>{year}</th>{''.join(cells)}</tr>")

    episodes = []
    for n in names:
        episodes.append(f'<h3><i style="background:{colors[n]}" class="dot"></i>{esc(n)}</h3><table><tr><th>Peak</th><th>Trough</th><th>Recovered</th><th>Depth</th><th>Sessions</th></tr>' +
                        "".join(f"<tr><td>{e['peak_date'][:10]}</td><td>{e['trough_date'][:10]}</td><td>{(e['recovery_date'] or 'not recovered')[:10] if e['recovery_date'] else 'not recovered'}</td>"
                                f"<td>{pct(e['drawdown'])}</td><td>{e['duration_sessions']}</td></tr>" for e in results[n]["episodes"]) + "</table>")

    css = """:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mute:#5b6573;--line:#dfe3e8;--warn:#c43d3d}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf2;--mute:#9aa5b4;--line:#2a313c;--warn:#e56b6b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:0 0 4px}h3{font-size:14px;margin:14px 0 6px}
.n{color:var(--mute);font-size:13px;margin:0 0 8px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:14px 0}
.warn{border-left:4px solid var(--warn)}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--mute);font-weight:600}td{font-variant-numeric:tabular-nums}svg{width:100%;height:auto;display:block}.grid{stroke:var(--line);stroke-width:1}
.zero{stroke:var(--mute);stroke-width:1}.band{stroke:var(--warn);stroke-width:1;stroke-dasharray:5 4}.axis{fill:var(--mute);font-size:11px}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--mute);margin-top:6px}.legend i,.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}
@media (max-width:640px){th,td{padding:5px 4px;font-size:13px}}"""
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Strategy profile through time</title><style>{css}</style></head><body><main>"
            "<h1>Strategy profile through time</h1><p class=n>Generated from saved daily equity paths with the repo's temporal and annual diagnostics. "
            "Descriptive history only.</p>"
            '<section class="card warn"><b>Read this first.</b><ul><li>This is viewed development history, so it is partly hindsight and is not evidence of future returns.</li>'
            "<li>The T11 paths come from QuantConnect cloud exports. Their local reproduction is blocked, so the strategy cannot be rerun here.</li>"
            "<li>Both T11 variants trade leveraged ETFs and start in 2020, a period that favored them; the gated variant still exceeds the 30% drawdown tolerance.</li>"
            "<li>No fees beyond the run's own cost assumptions are added, and no taxes.</li></ul></section>"
            f'<section class="card"><h2>Summary</h2><table>{head}{"".join(summary_rows)}</table></section>'
            + chart("Growth of USD 10,000 (log scale)", "Equity at each session close. A straight line on a log scale is a constant growth rate.",
                    line(lambda r: r["table"]["equity_usd"]), log=True)
            + chart("Drawdown from the running peak", "How far below the previous high the account sat on each day.",
                    line(lambda r: r["table"]["drawdown"]), zero=0, band=-TOLERANCE, cap_top=0)
            + chart("Rolling 1-year return (252 sessions)", "Return over the trailing 252 sessions; shows how much of the result came from a few strong stretches.",
                    line(lambda r: r["table"]["return_252"]), zero=0)
            + chart("Rolling 1-year Sharpe (zero risk-free)", "Return per unit of volatility over the trailing 252 sessions.",
                    line(lambda r: r["table"]["sharpe_252"]), zero=0, fmt=lambda v, d: f"{v:.1f}")
            + f'<section class="card"><h2>Calendar years</h2><p class=n>Each year\'s drawdown resets at the prior year-end.</p><table>{"".join(annual)}</table></section>'
            f'<section class="card"><h2>Deepest drawdown episodes</h2>{"".join(episodes)}</section>'
            "</main></body></html>")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--series", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--benchmark-csv", type=Path)
    parser.add_argument("--benchmark-name", default="SPY buy and hold")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/progress/profile.html")
    args = parser.parse_args(argv)
    paths = {}
    for item in args.series:
        name, sep, path = item.partition("=")
        if not sep:
            parser.error("--series needs NAME=PATH")
        paths[name] = load_path(path)
    first = next(iter(paths.values()))
    if args.benchmark_csv:
        paths[args.benchmark_name] = load_benchmark(args.benchmark_csv, first.index[0], first.index[-1], float(first.iloc[0]))
    results = {name: analyze(series) for name, series in paths.items()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(results, list(paths)))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
