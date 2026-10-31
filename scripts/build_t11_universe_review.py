#!/usr/bin/env python3
"""Render only captured universe results; no simulation, broker or MLflow writes."""
import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'full': 'T11 + risk gate', 'equal': 'Fixed equal-family + gate',
          'rs1': 'GATE-RS1 selector + gate'}


def main():
    rows = []
    for cost in (25, 50):
        for mode in ('full', 'equal', 'rs1'):
            case = mode + str(cost)
            if case == 'rs125':
                path = ROOT / '.local/t11-universe-cloud-v7/rs125/captured.partial.json'
            elif case == 'full25':
                path = ROOT / '.local/t11-universe-cloud-v10/full25/captured.partial.json'
            else:
                path = ROOT / f'.local/t11-universe-cloud-v11/{case}/captured.json'
            if not path.exists():
                continue
            result = json.loads(path.read_text())
            row = dict(result, mode=mode, cost_bps=cost, label=LABELS[mode])
            row['overall'] = result['records']['overall']
            rows.append(row)
    journal = json.loads((ROOT / '.local/t11-universe-cloud-v11/journal.json').read_text())
    if journal['used'] > 10:
        raise ValueError('Financial budget exceeded')
    output = ROOT / '.local/performance/t11-universe-v1'
    output.mkdir(exist_ok=True, parents=True)
    payload = dict(status='provisional_development_no_adoption', rows=rows,
                   missing_cases=[m+str(c) for c in (25,50) for m in ('full','equal','rs1') if not any(r['case_id']==m+str(c) for r in rows)],
                   financial_attempts=journal['used'], remaining=10-journal['used'],
                   independent_ledger_verified=False, official_daily_exports_verified=False,
                   source='docs/tasks/2026-10-30-t11-universe-comparison.md')
    (output/'comparison.json').write_text(json.dumps(payload, indent=2)+'\n')
    keys = ['case_id', 'label', 'cost_bps', 'calmar', 'cagr', 'dd', 'sharpe',
            'longest_sessions', 'longest_days', 'longest_censored', 'status', 'run_id']
    with (output/'comparison.csv').open('w') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row['overall'].get(k, row.get(k)) for k in keys})
    annual_keys = ['case_id', 'label', 'cost_bps', 'year', 'return', 'dd', 'annual_calmar',
                   'sharpe', 'longest_sessions', 'longest_days', 'longest_censored']
    annual = []
    for row in rows:
        for year in range(2020, 2026):
            if 'Y'+str(year) not in row['records']:
                continue
            annual.append(dict(case_id=row['case_id'], label=row['label'], cost_bps=row['cost_bps'],
                               **row['records']['Y'+str(year)]))
    with (output/'annual.csv').open('w') as f:
        writer = csv.DictWriter(f, annual_keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(annual)
    def num(v, percent=False):
        return '—' if v is None else f'{v*100:.2f}%' if percent else f'{v:.3f}'
    body = []
    for r in rows:
        m = r['overall']
        evidence = 'Partial audit; terminal details missing' if r.get('status')=='completed_capture_incomplete' or r['case_id']=='rs125' else 'Captured summaries; ledger unverified'
        if r['case_id'] == 'full25':
            evidence = 'Temporal/annual capture missing; audit incomplete'
        underwater = 'Missing in fresh capture' if m['longest_sessions'] is None else f"{m['longest_sessions']} / {m['longest_days']}"
        body.append(f'<tr data-cost="{r["cost_bps"]}"><td>{html.escape(r["label"])}</td>'
                    f'<td>{r["cost_bps"]}</td><td><strong>{num(m["calmar"])}</strong></td>'
                    f'<td>{num(m["cagr"],True)}</td><td>{num(abs(m["dd"]),True)}</td>'
                    f'<td>{num(m["sharpe"])}</td><td>{underwater}'
                    f'{" (censored)" if m["longest_censored"] else ""}</td><td>{evidence}</td></tr>')
    years = []
    for r in annual:
        years.append(f'<tr data-cost="{r["cost_bps"]}"><td>{r["year"]}</td><td>{html.escape(r["label"])}</td>'
                     f'<td>{r["cost_bps"]}</td><td>{num(r["return"],True)}</td><td>{num(abs(r["dd"]),True)}</td>'
                     f'<td>{num(r["annual_calmar"])}</td><td>{num(r["sharpe"])}</td>'
                     f'<td>{r["longest_sessions"]} / {r["longest_days"]}</td></tr>')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>T11 universe · bounded comparison</title><style>
body{font:16px system-ui;background:#f7f5ef;color:#192927;margin:32px;max-width:1500px}h1{font-size:30px}
.note{background:#fff0d5;padding:16px;border-left:4px solid #a65c16;line-height:1.6}table{border-collapse:collapse;width:100%;background:white;margin:20px 0;font-size:14px}
th,td{padding:12px;text-align:right;border-bottom:1px solid #dbe2de}th:first-child,td:first-child{text-align:left}thead{background:#dfece7}a{color:#145e4d}select{font:inherit;padding:8px}
</style><h1>T11 universe: results, not a promotion</h1>
<p>2020–2025 · USD10,000 · LEAN18222 · same staged execution and25/50bp costs · six ETF/cash universe</p>
<div class="note">Provisional viewed-history development. Independent ledger and official daily-export audits remain incomplete.
Headline Calmar uses custom closing-path CAGR/drawdown. Underwater duration includes recovery; it differs from older legacy counts.
The25bp selector has complete performance summaries but partial audit capture. Terminal next-open intents are disclosed; no post-window fills are assumed.
Ten slots exhausted; full50 submission unknown, equal50 and other planned controls omitted. Fresh T11 temporal and annual captures missing. No alpha, paper readiness or live authorization established.</div>
<p>Cost context: <select id="cost"><option value="all">Both</option><option>25</option><option>50</option></select>
 · <a href="comparison.csv">Overall CSV</a> · <a href="annual.csv">Annual CSV</a> · <a href="comparison.json">Evidence JSON</a></p>
<h2>Full period</h2><table><thead><tr><th>Policy</th><th>Cost bp</th><th>Calmar</th><th>CAGR</th><th>Max DD</th><th>Sharpe</th><th>Underwater sessions / days</th><th>Evidence</th></tr></thead><tbody>BODY</tbody></table>
<h2>Calendar years</h2><p>Annual Calmar = calendar-year return / absolute year-local drawdown, anchored at prior year close. Year-local recovery can be censored at year-end.</p>
<table><thead><tr><th>Year</th><th>Policy</th><th>Cost bp</th><th>Return</th><th>Max DD</th><th>Annual Calmar</th><th>Sharpe</th><th>Underwater sessions / days</th></tr></thead><tbody>YEARS</tbody></table>
<script>document.getElementById('cost').addEventListener('change',e=>document.querySelectorAll('[data-cost]').forEach(r=>r.hidden=e.target.value!=='all'&&r.dataset.cost!==e.target.value));</script></html>'''
    (output/'index.html').write_text(document.replace('BODY',''.join(body)).replace('YEARS',''.join(years)))
    print(json.dumps(dict(cases=len(rows), annual_rows=len(annual), attempts=journal['used'], output=str(output))))


if __name__ == '__main__':
    main()
