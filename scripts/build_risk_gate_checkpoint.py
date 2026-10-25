#!/usr/bin/env python3
"""Read-only financial evidence review; never runs a strategy or retries a case."""
from pathlib import Path
import json
import sys
import hashlib
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from reporting.temporal import analyze_temporal
from research.risk_gate_analysis import independent_temporal
from research.control_parity import compare
from scripts.recursive_research_review import inspect, verify_artifacts


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x): Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


def main():
    state_path=ROOT/'.local/rsi-risk-gate/state.json'; state=json.loads(state_path.read_text())
    source=ROOT/state['output']; out=ROOT/'.local/performance/risk-gate/20261025-checkpoint-v2'
    if out.exists(): raise ValueError('Preserve existing checkpoint; choose a new explicit version.')
    out.mkdir(parents=True)
    first=source/'5_hold'; old=ROOT/'reports/leverage/3aba31cfafe4da76/base_6pct_buy_hold_1x'
    parity=compare(pd.read_csv(old/'ledger.csv',index_col='date'),pd.read_csv(first/'ledger.csv',index_col='date'),
                   pd.read_csv(old/'trades.csv'),pd.read_csv(first/'trades.csv'))
    # First attempt remains FAILED: post-stop checker repair is read-only evidence,
    # not a reclassification, resume, successful full study or financial retry.
    write(source/'post-stop-control-parity.json',parity)
    labels={'hold':'Daily full-target control','ema':'Saved EMA50/200 reference'}
    folders={'hold':first,'ema':ROOT/'reports/strategy-suite/97fc0717512bee9e/s002_1x'}
    rows=[]; annual=[]; temporal={}; charts=[]; checks={}
    fig=make_subplots(rows=4,cols=1,shared_xaxes=True,vertical_spacing=.055,
        subplot_titles=('Net equity, USD','Drawdown from running peak, %','Rolling 252-session return, %','Rolling 252-session Sharpe'))
    colors={'hold':'#2454cf','ema':'#b05019'}
    for key,folder in folders.items():
        review=inspect(folder); curve=pd.read_csv(folder/'ledger.csv',index_col='date')
        eq=pd.Series(np.r_[300000,curve.equity_usd],index=pd.to_datetime(['2004-12-31',*curve.index]))
        t,table=analyze_temporal(eq,initial_capital=300000)
        checks[key]=dict(metric_checks=len(review['metric_checks']),temporal=independent_temporal(eq,t,table))
        r=review['overall']; temporal[key]=t
        rows.append(dict(Strategy=labels[key],CAGR=r['return_pct'],Drawdown=r['drawdown_pct'],Sharpe=r['sharpe'],Calmar=r['calmar'],
                         Underwater_sessions=t['longest_underwater_duration_sessions'],Underwater_calendar_days=t['longest_underwater_duration_calendar_days'],
                         Longest_censored=t['longest_underwater_right_censored'],Ending_USD=r['ending_equity_usd']))
        for a in review['annual']: annual.append(dict(Strategy=labels[key],**a))
        for n,col,mult in ((1,'equity_usd',1),(2,'drawdown',100),(3,'return_252',100),(4,'sharpe_252',1)):
            fig.add_trace(go.Scatter(x=table.index,y=table[col]*mult,name=labels[key],legendgroup=key,
                                    showlegend=n==1,line=dict(color=colors[key],width=1.3)),row=n,col=1)
    fig.update_layout(height=950,template='plotly_white',margin=dict(l=70,r=25,t=50,b=45),legend=dict(orientation='h',y=1.06))
    fig.write_html(out/'comparison.html',include_plotlyjs='directory',full_html=True)
    temporal_rows=[]
    for key,t in temporal.items():
        row={'Strategy':labels[key],'Historical daily ES95 loss %':t['historical_daily_es95']['loss_magnitude']*100}
        for w in (1,5,21,63): row[f'Worst {w}-session return %']=100*t['worst_returns'][str(w)]['return']
        temporal_rows.append(row)
    bundle=dict(temporal_method='temporal-v1.2',status='STOPPED_INCOMPLETE',new_financial_attempts=1,failed_attempts=1,unstarted_cases=11,
                reason='Legacy 14-column control vs current 15-column ledger triggered whole-frame schema assertion.',
                post_stop_read_only_parity=parity,checks=checks,rows=rows,annual=annual,temporal=temporal,
                tested_gate_performance=False,followup_launched=False,
                sources={key:str(f.relative_to(ROOT)) for key,f in folders.items()},
                source_hashes={str(f.relative_to(ROOT)):sha(f) for folder in folders.values() for f in sorted(folder.iterdir()) if f.is_file()},
                generated_utc=datetime.now(timezone.utc).isoformat())
    write(out/'review-bundle.json',bundle)
    table=pd.DataFrame(rows).to_html(index=False,float_format=lambda x:f'{x:,.3f}',border=0)
    tmp=pd.DataFrame(temporal_rows).to_html(index=False,float_format=lambda x:f'{x:,.3f}',border=0)
    at=pd.DataFrame(annual)[['period','Strategy','return_pct','drawdown_pct','sharpe','calmar']].rename(columns={'period':'Year','return_pct':'Return %','drawdown_pct':'Drawdown %','sharpe':'Sharpe','calmar':'Calmar'}).to_html(index=False,float_format=lambda x:f'{x:,.3f}',border=0,table_id='annual')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Risk gate — bounded improvement checkpoint</title><style>
    body{font:16px/1.55 system-ui;color:#172438;background:#f3f5fa;margin:auto;max-width:1250px;padding:32px}h1{font-size:34px;line-height:1.2}h2{margin-top:32px}section{background:white;padding:24px;margin:20px 0;border-radius:12px} .flag{background:#fff0d2;border-left:5px solid #b96d00;padding:18px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:10px;text-align:right;border-bottom:1px solid #dce1e8}td:first-child,th:first-child{text-align:left} .scroll{overflow:auto}a{color:#214bc4}iframe{border:0;width:100%;height:990px}code{word-break:break-all}.muted{color:#516176}</style>
    <h1>Risk gate: bounded improvement checkpoint</h1><p class="muted">Viewed SPY development history · 2005–2025 · USD 300,000 · no new broker connection</p>
    <div class="flag"><strong>Study stopped — no gate performance conclusion.</strong><br>One financial attempt failed the legacy-schema comparison; 11 cases were never started. Accounting replay and metrics passed. A read-only repair confirms every shared control field matches. No automatic retry or follow-up was launched.</div>
    <section><h2>The goal</h2><p>Test whether a fixed green/yellow/red cap improves both maximum drawdown and longest observed underwater duration versus its own daily-long or EMA base at both 5 and 10 bps per side. Expose sacrificed growth, false alarms and missed rebounds. Rejecting a candidate is useful research progress.</p>
    <pre>Freeze → behavior checks → reserved simulations → independent audits → diagnose → one justified follow-up or stop</pre>
    <p>Maximum 16 new cases across at most two studies. Initial study: six rules × two costs, 12 cases. Failures count. One worker, 900 seconds per study. The stop rule has been triggered; the remaining budget is not permission to bypass it.</p></section>
    <section><h2>Verified references, not completed gate results</h2><p>The daily-long row is the saved first attempt, reproduced from the older control. The EMA row is a saved historical reference reviewed without running a new simulation. Both use 5 bps per side and $1 per net trade. “Hold” below resizes daily; literal buy-once holding was not run.</p><div class="scroll">'''+table+'''</div><p>Return and drawdown are percentages. CAGR is annualized across the full history. Calmar divides CAGR by drawdown magnitude. Sharpe uses daily returns, sample standard deviation, √252 and zero risk-free rate. Underwater duration counts observed sessions; unresolved recoveries remain censored.</p></section>
    <section><h2>Compare the paths</h2><p>Zoom or toggle a legend to compare equity, depth of loss and rolling one-year behavior.</p><iframe title="Historical equity and temporal comparison" src="comparison.html"></iframe></section>
    <section><h2>Temporal losses</h2><div class="scroll">'''+tmp+'''</div><p>ES95 is the mean loss in the worst ceil(5% × 5,283) observed daily returns. Windows are cumulative observed-session returns, not forecasts or future loss limits.</p></section>
    <section><h2>Year by year</h2><label for="year">Year: </label><select id="year"><option value="all">All years</option>'''+''.join(f'<option>{y}</option>' for y in range(2005,2026))+'''</select><div class="scroll">'''+at+'''</div><p>Annual return and drawdown anchor to the previous year-end equity. No strategy is refit or restarted at year boundaries.</p></section>
    <section><h2>What improved, and what remains</h2><p>Implemented: causal state machine, strict timing/caps, literal entry-only holding, finite/coverage guards and independent temporal checks. Found and repaired: a schema-sensitive legacy parity checker and rolling variance residue that displayed zero Sharpe for flat cash windows. This review uses temporal-v1.2; old reports stay unchanged. Not established: gate protection, 10 bps robustness, event outcomes, annual doubling, financial alpha or a trained RL advantage.</p><p>Next admissible decision: review a separately frozen repair/re-entry plan before another financial run. Keep the failed case and its original plan unchanged. No threshold changes are justified by this failure.</p><p><a href="review-bundle.json">Machine-readable review</a> · <a href="manifest.json">Artifact manifest</a> · <a href="../../recursive-research/20261025-review-v3/index.html">Prior completed research review</a></p></section>
    <script>document.getElementById('year').onchange=function(){for(const r of document.querySelectorAll('#annual tbody tr'))r.hidden=this.value!=='all'&&r.cells[0].innerText!==this.value}</script></html>'''
    (out/'index.html').write_text(html)
    state.update(status='stopped_checker_repaired_not_rerun',actual_financial_attempts=1,failed_attempts=1,unstarted_cases=11,
                 followup_launched=False,stop_reason=bundle['reason'],checkpoint=str(out.relative_to(ROOT)),
                 post_stop_code_hashes={f:sha(ROOT/f) for f in ('research/risk_gate_study.py','research/control_parity.py','tests/test_control_parity.py')})
    write(state_path,state)
    write(source/'manifest.json',dict(status='STOPPED_INCOMPLETE',artifact_hashes={str(f.relative_to(source)):sha(f) for f in sorted(source.rglob('*')) if f.is_file() and f.name!='manifest.json'}))
    write(out/'manifest.json',dict(status='STOPPED_INCOMPLETE',artifact_hashes={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest.json'}))
    print(json.dumps(dict(report=str(out),financial_evidence=verify_artifacts(source),report_evidence=verify_artifacts(out),references=rows),indent=2))

if __name__=='__main__': main()
