#!/usr/bin/env python3
"""Render saved UI observations only. No simulations, network, imports or orders."""
import csv
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reporting.soxl_review import observed_case


def main():
    evidence=ROOT/'.local/t11-soxl-cloud-v1'
    plan=json.loads((evidence/'frozen-plan.json').read_text())
    journal=json.loads((evidence/'journal.json').read_text())
    output=ROOT/'.local/performance/t11-soxl-cloud-v1';output.mkdir(parents=True,exist_ok=True)
    rows=[];artifacts=[]
    for case in plan['cases']:
        name=case['case'];attempt=next((a for a in journal['attempts'] if a['case']==name),None)
        source=ROOT/case['source']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=case['source_sha256']:
            raise ValueError('Frozen source changed: '+name)
        if not attempt or not attempt.get('run_id') or not attempt['status'].startswith('completed'):
            raise ValueError('Case not captured/completed: '+name)
        path=evidence/name/'observed-ax.txt'
        if path.exists():
            row=observed_case(path.read_text(),name,attempt['run_id'])
        else:
            path=evidence/name/'manual-ui-observation.json'
            row=json.loads(path.read_text())
            if row['case']!=name or row['run_id']!=attempt['run_id']:raise ValueError('Observation identity mismatch')
        row.update(cost_bps=25 if name.endswith('25bp') else 50,
                   source_sha256=case['source_sha256'],raw_ui_evidence=str(path.relative_to(ROOT)))
        rows.append(row)
        artifacts.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    result={'status':'incomplete_export_and_daily_path_audit','launched_cases':journal['used'],'max_cases':8,
            'completed_cases':len(rows),'financial_retries':0,'rows':rows,'artifacts':artifacts,
            'limitations':['Official JSON exports not captured: browser frame/download failures.',
                           'Native overview metrics and custom close summaries use different conventions; kept separate.',
                           'Missing/truncated values are unavailable, never zero or completed from guesses.',
                           'No independently reconciled daily equity, orders/accounting or original daily-decision parity.',
                           'No promotion, new alpha or paper readiness established. Viewed-history development only.']}
    (evidence/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    (output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    with (output/'comparison.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['case','cost_bps','evidence','native_CAGR_pct','native_DD_pct','derived_native_Calmar','native_Sharpe','ending_NAV','orders','legacy_UW_sessions_partial','legacy_UW_days_partial'])
        for r in rows:
            n=r['native'];t=r['custom_partial'];writer.writerow([r['case'],r['cost_bps'],r['evidence_status'],n['Compounding Annual Return'],n['Drawdown'],n['derived_calmar_from_rounded_native_statistics'],n['Sharpe Ratio'],n['End Equity'],n['Total Orders'],t.get('legacy_longest_underwater_sessions'),t.get('legacy_longest_underwater_calendar_days')])
    annual=[dict(case=r['case'],cost_bps=r['cost_bps'],**a) for r in rows for a in r['annual_partial']]
    with (output/'annual-partial.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['case','cost_bps','year','return_pct','drawdown_pct','sharpe','annual_calmar']);w.writeheader();w.writerows(annual)
    def fmt(value):return 'Unavailable' if value is None else f'{value:,.3f}'
    labels={'gated_t11':'T11 + risk gate','soxl_cash_ungated':'SOXL / cash','soxl_cash_gated':'SOXL / cash + gate','soxl_buy_hold':'SOXL buy and hold'}
    def label(case):return labels[case.rsplit('_',1)[0]]
    table=''
    for r in rows:
        n=r['native'];t=r['custom_partial']
        table+='<tr data-cost="'+str(r['cost_bps'])+'"><td>'+html.escape(label(r['case']))+'</td><td>'+str(r['cost_bps'])+'</td>'
        table+=''.join('<td>'+fmt(x)+'</td>' for x in [n['derived_calmar_from_rounded_native_statistics'],n['Compounding Annual Return'],n['Drawdown'],n['Sharpe Ratio'],n['End Equity'],t.get('legacy_longest_underwater_sessions'),t.get('legacy_longest_underwater_calendar_days')])
        table+='<td>Provisional UI capture</td></tr>'
    partial=''.join('<tr><td>'+html.escape(label(a['case'])+' · '+str(a['cost_bps'])+'bp')+'</td><td>'+str(a['year'])+'</td>'+''.join('<td>'+fmt(a[k])+'</td>' for k in ['return_pct','drawdown_pct','sharpe','annual_calmar'])+'</tr>' for a in annual)
    # Verify the displayed comparison claim against both actual cost groups.
    for bp in (25, 50):
        group=[r for r in rows if r['cost_bps']==bp]
        baseline=next(r for r in group if r['case']==f'gated_t11_{bp}bp')
        if not all(baseline['native']['derived_calmar_from_rounded_native_statistics'] > r['native']['derived_calmar_from_rounded_native_statistics'] for r in group if r is not baseline):
            raise ValueError('Displayed T11-leading conclusion is unsupported')
    # Inline SVG is entirely local; no external script or analytics dependencies.
    bars=''
    for i,r in enumerate(rows):
        y=28+i*34;n=r['native'];calmar=n['derived_calmar_from_rounded_native_statistics']
        bars+=f'<text x="0" y="{y+12}" fill="#1e293b" font-size="12">{html.escape(label(r["case"])+" · "+str(r["cost_bps"])+"bp")}</text><rect x="240" y="{y}" width="{max(0,calmar or 0)*190:.2f}" height="20" fill="{("#0f766e" if r["cost_bps"]==25 else "#b45309")}"/><text x="{247+max(0,calmar or 0)*190:.2f}" y="{y+14}" font-size="12">{fmt(calmar)}</text>'
    document='''<!doctype html><html><head><meta charset="utf-8"><title>T11 · SOXL or cash — provisional comparison</title><style>body{font:16px system-ui;background:#f7f7f2;color:#17212b;margin:36px;max-width:1500px}h1{font-size:30px}.notice{background:#fff0cf;border:1px solid #b45309;padding:16px;border-radius:12px}table{border-collapse:collapse;background:white;width:100%;margin:20px 0;font-size:14px}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}th{background:#dbe8e3}a{color:#075985}button,select{padding:8px}.muted{color:#56616b}svg{max-width:100%;background:white;padding:15px;border-radius:12px}</style></head><body><h1>T11 signals → SOXL or cash → risk cap</h1><p>2020–2025 · $10,000 · 90% target before gate · original staged MOO execution · 6% debit ACT/360 · LEAN 18217</p><p class="notice"><strong>Eight financial cases completed; export audit incomplete.</strong> These are captured native summaries, not independently audited daily paths. No SOXL strategy beats full gated T11 in this comparison. The gate is a target cap, not a guaranteed loss limit.</p><p>Cost filter <select id="cost"><option value="all">Both costs</option><option value="25">25bp</option><option value="50">50bp</option></select> · <a href="comparison.csv">Comparison CSV</a> · <a href="annual-partial.csv">Partial annual CSV</a> · <a href="comparison.json">Evidence and missing fields</a></p><h2>Same-convention native overview comparison</h2><p class="muted">Headline Calmar here is calculated from rounded native CAGR / native drawdown. It differs slightly from our custom daily-close Calmar. Do not merge these rows into that ranking. Underwater columns are explicitly legacy fragments excluding recovery; missing calendar durations remain unavailable.</p><table><thead><tr><th>Case</th><th>Cost bp</th><th>Derived Calmar</th><th>CAGR %</th><th>Max DD %</th><th>Sharpe</th><th>Ending NAV $</th><th>Legacy UW sessions</th><th>Legacy UW days</th><th>Evidence</th></tr></thead><tbody>'''+table+'''</tbody></table><h2>Calmar and cost sensitivity</h2><p>Teal:25bp; amber:50bp. Rounded native convention throughout this chart.</p><svg viewBox="0 0 900 315" role="img" aria-label="Calmar comparison at two trading costs">'''+bars+'''</svg><h2>Partial annual custom-close observations</h2><p class="muted">Annual return / within-year drawdown; sample daily Sharpe, zero risk-free. Truncated log lines are not full audit receipts. Missing case-years are absent, not zero. No complete temporal-v1.2 analysis is available without official daily equity exports.</p><table><thead><tr><th>Case</th><th>Year</th><th>Return %</th><th>Max DD %</th><th>Sharpe</th><th>Annual Calmar</th></tr></thead><tbody>'''+partial+'''</tbody></table><h2>Interpretation and next evidence</h2><p>SOXL/cash removes every T11 branch that does not select SOXL, including inverse and defensive allocations. This is a concentrated long/cash variant, not the original strategy traded through another ticker. The gate comparison isolates its cap within that narrower policy. Exact missed-rebound attribution requires daily decisions and order/equity exports.</p><p><a href="https://www.quantconnect.com/project/38676621">Own QuantConnect test project</a> · No broker connections or orders. Eight-case ceiling exhausted; no automatic retries or parameter tuning.</p><script>document.getElementById('cost').onchange=function(){document.querySelectorAll('tr[data-cost]').forEach(r=>r.hidden=this.value!=='all'&&r.dataset.cost!==this.value)}</script></body></html>'''
    (output/'index.html').write_text(document)
    print(json.dumps({'completed':len(rows),'annual_rows_captured':len(annual),'url':'http://127.0.0.1:8765/t11-soxl-cloud-v1/index.html','status':result['status']}))

if __name__=='__main__':main()
