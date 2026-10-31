#!/usr/bin/env python3
"""Describe saved reference close paths; no data retrieval or financial simulation."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reporting.temporal import analyze_temporal

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / '.local/t11-reference-v2/export-review-v2'
    reference = json.loads((source / 'comparison.json').read_text())
    results = {}
    paths = {}
    for name in ('t11', 'gated_t11'):
        file = source / (name + '-candidate-close-path.json')
        rows = json.loads(file.read_text())
        equity = pd.Series([10000.] + [r['nav_usd'] for r in rows],
                           index=pd.to_datetime(['2019-12-31'] + [r['session'] for r in rows]))
        summary, _ = analyze_temporal(equity, initial_capital=10000.)
        if len(rows) != 1508 or abs(equity.iloc[-1] - reference[name]['metrics_legacy']['end']) > .01:
            raise ValueError('Reference coverage or ending NAV mismatch')
        growth = np.log(equity / equity.shift(1)).dropna()
        years = [dict(year=int(year), return_fraction=float(np.expm1(part.sum())),
                      log_growth=float(part.sum()), share_of_log_growth=float(part.sum()/growth.sum()))
                 for year, part in growth.groupby(growth.index.year)]
        results[name] = dict(source=str(file.relative_to(ROOT)),
                             sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                             temporal=summary, annual_log_growth=years,
                             top10_day_share_of_log_growth=float(growth.nlargest(10).sum()/growth.sum()))
        paths[name] = equity
    if not paths['t11'].index.equals(paths['gated_t11'].index):
        raise ValueError('Different reference calendars')
    dates = ('2025-01-27', '2025-04-09', '2020-03-24')
    results['selected_retrospective_sessions'] = {
        name: {date: float(eq.pct_change().loc[date]) for date in dates} for name, eq in paths.items()}
    results['status'] = 'descriptive_saved_path_diagnosis_no_financial_runs'
    results['limitations'] = ['Reconstructed export closing paths, not original engine daily traces',
                              'No branch-level causal PnL attribution',
                              'Viewed development history; selected dates are retrospective']
    output = ROOT / '.local/t11-diagnosis-v1'
    output.mkdir(exist_ok=True)
    (output / 'saved-path-diagnosis.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(dict(status=results['status'], sessions=1508, output=str(output))))


if __name__ == '__main__':
    main()
