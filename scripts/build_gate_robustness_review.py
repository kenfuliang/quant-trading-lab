#!/usr/bin/env python3
"""Read-only saved-epoch report; no simulations, services or tracking imports."""
import argparse
import html
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from research.gate_robustness import CASES, old
from scripts.recursive_research_review import verify_artifacts


def build(source, output):
    verified = verify_artifacts(source)
    state = json.loads((source / 'state.json').read_text())
    decision = json.loads((source / 'decision.json').read_text())
    if (state['status'] != 'completed' or state['actual_attempts'] != 9 or
            [a['id'] for a in state['attempts']] != [c['id'] for c in CASES] or
            any(a['status'] != 'completed' for a in state['attempts'])):
        raise ValueError('Incomplete epoch; do not publish a passing review.')
    counts = dict(decimal_sessions=0, metric_checks=0, temporal_scalar_window_checks=0)
    exposure = []
    for case in CASES:
        folder = source / case['id']
        audit = json.loads((folder / 'audit.json').read_text())
        temporal = json.loads((folder / 'temporal-audit.json').read_text())
        if not audit['passed'] or not temporal['passed']:
            raise ValueError('Failed audit.')
        # Fresh read-only arithmetic verification of saved annual/full-period scores.
        metrics = old.inspect(folder)
        counts['decimal_sessions'] += audit['sessions']
        counts['metric_checks'] += len(metrics['metric_checks'])
        counts['temporal_scalar_window_checks'] += temporal['scalar_and_window_checks']
        exposure.append(dict(id=case['id'], **{key: metrics['overall'][key] for key in
            ('mean_close_exposure', 'fraction_sessions_invested', 'trades',
             'commission_usd', 'slippage_usd', 'dividend_usd')}))
    overall = pd.read_csv(source / 'overall.csv')
    annual = pd.read_csv(source / 'annual.csv')
    blocks = pd.read_csv(source / 'blocks.csv')
    win_counts = {}
    for context in ('base', 'expensive', 'delayed'):
        pair = annual.loc[annual.context.eq(context)].pivot(index='period', columns='rule', values='return_pct')
        win_counts[context] = dict(years=21, gate_higher_return_years=int((pair.gate_ema > pair.ema).sum()),
                                   ema_higher_return_years=int((pair.ema > pair.gate_ema).sum()),
                                   ties=int((pair.ema == pair.gate_ema).sum()))
    output.mkdir(parents=True, exist_ok=False)
    for name in ('overall.csv', 'annual.csv', 'blocks.csv', 'decision.json'):
        shutil.copyfile(source / name, output / name)
    pd.DataFrame(exposure).to_csv(output / 'exposure-costs.csv', index=False)
    table = overall[['context', 'rule', 'return_pct', 'drawdown_pct', 'sharpe', 'calmar',
                     'duration', 'right_censored', 'worst_21_return_pct', 'daily_es95_pct']].rename(
        columns={'return_pct': 'CAGR %', 'drawdown_pct': 'Max DD %', 'duration': 'Recovery intervals',
                 'worst_21_return_pct': 'Worst 21 sessions %', 'daily_es95_pct': 'Daily ES95 %'})
    def show(data):
        return data.to_html(index=False, float_format=lambda x: f'{x:.3f}', border=0, escape=True)
    body = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Frozen SPY gate — execution robustness</title><style>
body{{font:16px/1.5 system-ui;background:#f7f4ea;color:#172c29;margin:40px;max-width:1500px}}
h1,h2{{line-height:1.2}}.result{{background:#dcebd8;padding:24px;border-radius:16px;border:1px solid #698b6c}}
.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px;background:#fffdf6}}
th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:right}}th{{background:#e3eaf2}}
pre{{background:#eee9db;padding:16px;overflow:auto}}a{{color:#195e70}}
</style><h1>Frozen SPY gate: execution robustness</h1>
<p>2005–2025 · previously viewed development history · USD300,000 · nominal1x</p>
<div class="result"><b>Retain for independent validation.</b> All three fixed comparisons passed against EMA.
Nine attempts completed, no retries. No new strategy parameters, trained model or independent alpha established.</div>
<pre>Freeze → reserve 9 paths → one worker → account/metric audits → diagnose → stop</pre>
<p>Base:5bp/side. Expensive:25bp/side. Delayed:25bp plus one extra observed session for both dynamic
rules. Buy-and-hold has no recurring signal; its last two paths are duplicate controls. USD1/net trade,
99% sizing reserve, zero cash interest, ex-date dividend-cash approximation and final marked holdings.
These are assumptions, not measured broker costs. No broker/native execution parity.</p>
<h2>Overall comparison</h2><div class="scroll">{show(table)}</div>
<p>Recovery intervals measure longest observed peak-to-recovery/censor duration, not the duration of
the deepest drawdown alone. Max DD is daily-close equity drawdown with initial capital included.
Sharpe uses252 sessions/year and zero risk-free rate; Calmar is CAGR/absolute max DD.
ES95 is the average of the worst5% daily returns, not a future loss limit.</p>
<h2>Where the gate loses</h2>
<p>Buy-and-hold has higher full-period growth in every context. The gate underperforms EMA in the
2012–2018 block in all contexts; aggregate success does not imply superiority every year or regime.
Lower exposure can explain much of the risk reduction; matched-risk alpha remains untested.</p>
<pre>{html.escape(json.dumps(win_counts, indent=2))}</pre>
<h2>Year-by-year</h2><p>Annual return and within-year drawdown use previous year-end equity as anchor.
Annual Calmar uses annual return; it is distinct from full-period CAGR-based Calmar.</p>
<div class="scroll">{show(annual[['context','rule','period','return_pct','drawdown_pct','sharpe','calmar']])}</div>
<h2>Viewed chronological blocks</h2><p>Continuous accounts, no reset/refit. Returns below are cumulative,
not annualized. The preserved raw blocks.csv helper's calmar field is cumulative return/absolute DD;
it is excluded here and from rankings because it is not annualized Calmar.</p>
<div class="scroll">{show(blocks[['context','rule','start','end','sessions','return_pct','drawdown_pct','sharpe']])}</div>
<h2>Exposure and cost</h2><div class="scroll">{show(pd.DataFrame(exposure))}</div>
<h2>Next evidence gate</h2><p>Freeze this candidate and selection history before genuinely unviewed,
qualified chronological observations become available. Qualify dividend payment dates, calendar and
execution assumptions first. Do not tune against another slice of the same history and call it a holdout.
The nine-path financial budget is exhausted; no automatic next study or promotion.</p>
<p><a href="overall.csv">Overall CSV</a> · <a href="annual.csv">Annual CSV</a> ·
<a href="blocks.csv">Raw block CSV</a> · <a href="exposure-costs.csv">Exposure/cost CSV</a> ·
<a href="decision.json">Fixed decision</a></p></html>'''
    (output / 'index.html').write_text(body)
    receipt = dict(status='completed', source=str(source), output=str(output),
                   source_manifest=verified, actual_financial_attempts=9, failed_attempts=0,
                   wall_seconds=state['elapsed_seconds'], audits=counts, annual_return_win_counts=win_counts,
                   decision=decision, block_ratio_warning='Raw blocks calmar is cumulative return/DD, not annualized Calmar; excluded from ranks.',
                   financial_budget_remaining=0,
                   artifact_hashes={str(f.relative_to(output)): old.digest(f) for f in sorted(output.iterdir()) if f.is_file()})
    old.write(output / 'manifest.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2, allow_nan=False))
