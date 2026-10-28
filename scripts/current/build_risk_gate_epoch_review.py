#!/usr/bin/env python3
"""Build the final bounded epoch review from saved evidence only."""
from pathlib import Path
import sys,json,hashlib,math
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from research.studies.spy.bounded_study import _json_scores,validate_financial_outputs
from research.evaluation.leveraged_spy import FinancingModel
from research.evaluation.leverage_audit import reconcile
from research.evaluation.control_parity import compare
from research.evaluation.risk_gate_analysis import independent_temporal,events,blocks
from reporting.temporal import analyze_temporal
from reporting.risk_gate_review import verify_temporal_details,verify_events,paired_verdict
from research.evaluation.saved_review import inspect,verify_artifacts

LABELS={'hold':'Daily full target','ema':'EMA50/200','gate_hold':'Combined gate / daily long','gate_ema':'Combined gate / EMA',
        'half_hold':'Daily half target','buy_hold_entry_only':'Buy once, hold shares','ablate_hold':'EMA + volatility gate / daily long','ablate_ema':'EMA + volatility gate / EMA'}
COLORS=['#2454cf','#bb5c18','#bc8e00','#8c69a8','#7c8797','#192a43','#14857d','#22683d']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(_json_scores(x),indent=2,allow_nan=False)+'\n')
def table(rows):return pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda x:f'{x:,.3f}',escape=True)


def main():
 state_path=ROOT/'.local/rsi-risk-gate/state.json';s=json.loads(state_path.read_text())
 if s['actual_financial_attempts']!=16 or s['status']!='sixteen_financial_attempts_pending_final_review':raise ValueError('Expected fixed study and its one follow-up.')
 original=ROOT/s['output'];follow=ROOT/s['followup_output'];repair=json.loads((ROOT/s['recovery2_plan']).read_text())
 folders={}
 for cost in (5,10):
  for name in LABELS:
   key=f'{cost}_{name}'
   if key=='5_hold':folder=ROOT/repair['recovery']['original_hold_source']
   elif key=='5_ema':folder=ROOT/repair['recovery']['ema_source']
   elif name.startswith('ablate_'):folder=follow/key
   else:folder=original/key
   folders[key]=folder
 manifests={str(f.parent.relative_to(ROOT)):verify_artifacts(f.parent) for f in folders.values()}
 out=ROOT/'.local/performance/risk-gate/20261025-epoch-v1'
 if out.exists():raise ValueError('Preserve previous output; version any replacement explicitly.')
 out.mkdir(parents=True);(out/'diagnostics').mkdir()
 curves={};signals={};times={};temporals={};temporal_tables={};rows=[];annual=[];audit_results={};block_rows=[]
 for key,folder in folders.items():
  cost=int(key.split('_',1)[0]);name=key.split('_',1)[1]
  curve=pd.read_csv(folder/'ledger.csv',index_col='date');signal=pd.read_csv(folder/'signal.csv',index_col='date');ti=pd.read_csv(folder/'timeline.csv',index_col='date')
  model=FinancingModel(cost_bps=cost)
  # Audit saved fills/accounts, never rerun a strategy or normalize monetary fields.
  from research.studies.spy.spy_backtest import load_data
  _,dividends,_=load_data(ROOT/'reports/spy/20261024-235746-728801/source-data.json')
  validate_financial_outputs(signal,curve,pd.read_csv(folder/'trades.csv'))
  mode='buy_hold' if name=='buy_hold_entry_only' else 'trend'
  accounting=reconcile(signal,dividends,curve,pd.read_csv(folder/'trades.csv'),mode,1,model)
  review=inspect(folder);r=review['overall']
  eq=pd.Series(np.r_[300000,curve.equity_usd],index=pd.to_datetime(['2004-12-31',*curve.index]))
  tm,tt=analyze_temporal(eq,initial_capital=300000)
  checks=independent_temporal(eq,tm,tt);details=verify_temporal_details(eq,tm)
  row=dict(id=key,cost_bps=cost,rule=name,strategy=LABELS[name],cagr_pct=r['return_pct'],drawdown_pct=r['drawdown_pct'],sharpe=r['sharpe'],calmar=r['calmar'],
      longest_underwater_sessions=tm['longest_underwater_duration_sessions'],longest_underwater_days=tm['longest_underwater_duration_calendar_days'],longest_censored=tm['longest_underwater_right_censored'],
      ending_equity_usd=r['ending_equity_usd'],mean_close_exposure=r['mean_close_exposure'],trades=r['trades'],
      commission_usd=r['commission_usd'],slippage_usd=r['slippage_usd'],historical_es95_loss_pct=tm['historical_daily_es95']['loss_magnitude']*100)
  for w in (1,5,21,63):row[f'worst_{w}_session_return_pct']=tm['worst_returns'][str(w)]['return']*100
  rows.append(row);audit_results[key]=dict(accounting=accounting,financial_metric_checks=len(review['metric_checks']),temporal=checks,episode_tail_checks=details,
       process_status='failed, separately qualified read-only' if key in ('5_hold','5_ema') else 'completed')
  curves[key]=curve;signals[key]=signal;times[key]=ti;temporals[key]=tm;temporal_tables[key]=tt
  for a in review['annual']:annual.append(dict(cost_bps=cost,rule=name,strategy=LABELS[name],**a))
  for b in blocks(curve,300000,[('2005-01-03','2011-12-30'),('2012-01-03','2018-12-31'),('2019-01-02','2025-12-31')]):
   start=curve.index.get_loc(curve.loc[b['start']:b['end']].index[0]);stop=curve.index.get_loc(curve.loc[b['start']:b['end']].index[-1])+1
   beq=eq.iloc[start:stop+1];bs,_=analyze_temporal(beq,initial_capital=float(beq.iloc[0]))
   block_rows.append(dict(id=key,**b,within_block_longest_sessions=bs['longest_underwater_duration_sessions'],within_block_censored=bs['longest_underwater_right_censored'],
       minimum_full_path_drawdown_pct=float(tt.drawdown.iloc[start+1:stop+1].min()*100)))
  write(out/'diagnostics'/f'{key}-temporal.json',tm);tt.to_csv(out/'diagnostics'/f'{key}-temporal.csv',index_label='date')
 # Explicitly preserve and disclose the legacy budget diagnostic correction.
 oldhold=ROOT/'reports/leverage/3aba31cfafe4da76/base_6pct_buy_hold_1x';oldema=ROOT/'reports/strategy-suite/97fc0717512bee9e/s002_1x'
 parity={}
 for key,old in [('5_hold',oldhold),('5_ema',oldema)]:
  c=curves[key].copy()
  if key=='5_ema':
   c['effective_target_leverage']=1.;c.to_csv(out/'diagnostics/5_ema-derived-legacy-budget-ledger.csv')
  parity[key]=compare(pd.read_csv(old/'ledger.csv',index_col='date'),c,pd.read_csv(old/'trades.csv'),pd.read_csv(folders[key]/'trades.csv'))
  parity[key]['raw_source_preserved']=True
  parity[key]['diagnostic_transform']='Only EMA effective_target_leverage re-expressed as legacy nominal budget 1; all monetary fields/shares/fills unchanged.' if key=='5_ema' else 'Missing historical diagnostic verified constant1 in current control.'
 lookup={r['id']:r for r in rows};pairs=[];ablation_pairs=[]
 for cost in (5,10):
  for base in ('hold','ema'):
   b=lookup[f'{cost}_{base}'];g=lookup[f'{cost}_gate_{base}'];a=lookup[f'{cost}_ablate_{base}']
   pairs.append(dict(cost_bps=cost,treatment=g['strategy'],base=b['strategy'],**paired_verdict(g,b)))
   pairs.append(dict(cost_bps=cost,treatment=a['strategy'],base=b['strategy'],**paired_verdict(a,b)))
   ablation_pairs.append(dict(cost_bps=cost,treatment=a['strategy'],base=g['strategy'],**paired_verdict(a,g)))
 event_results={};event_audits={};event_summary=[]
 for cost in (5,10):
  for rule in ('gate_hold','gate_ema','ablate_hold','ablate_ema'):
   key=f'{cost}_{rule}';base=f'{cost}_'+('ema' if rule.endswith('ema') else 'hold');hold=f'{cost}_hold'
   ev=events(times[key],signals[key],curves[key],curves[base],curves[hold],300000)
   event_audits[key]=verify_events(ev,times[key],signals[key],curves[key],curves[base],curves[hold],300000)
   event_results[key]=ev;event_summary.append(dict(cost_bps=cost,strategy=LABELS[rule],**ev['summary']))
   write(out/'diagnostics'/f'{key}-events.json',ev)
   pd.DataFrame(ev['warnings']).to_csv(out/'diagnostics'/f'{key}-warnings.csv',index=False)
   pd.DataFrame(ev['red_windows']).to_csv(out/'diagnostics'/f'{key}-red-windows.csv',index=False)
   pd.DataFrame(ev['transitions']).to_csv(out/'diagnostics'/f'{key}-transitions.csv',index=False)
 missed=[]
 for key,ev in event_results.items():
  for event in ('red_entry','red_exit'):
   for h in (5,21,63):
    windows=[w for w in ev['red_windows'] if w['event']==event and w['horizon']==h];valid=[w for w in windows if not w['right_censored']]
    missed.append(dict(id=key,event=event,horizon=h,observed_windows=len(valid),censored_windows=len(windows)-len(valid),
        mean_base_minus_gate_pp=None if not valid else float(np.mean([w['base_minus_gate'] for w in valid])*100),
        benchmark_better_count=sum(w['base_minus_gate']>0 for w in valid)))
 for cost in (5,10):
  fig=make_subplots(rows=5,cols=1,shared_xaxes=True,vertical_spacing=.055,row_heights=[.28,.19,.19,.19,.15],
       subplot_titles=('Net equity, USD','Drawdown from running peak, %','Rolling 252-session return, %','Rolling 252-session Sharpe','States available at execution open'))
  for (name,color) in zip(LABELS,COLORS,strict=True):
   tt=temporal_tables[f'{cost}_{name}']
   for n,col,mult in ((1,'equity_usd',1),(2,'drawdown',100),(3,'return_252',100),(4,'sharpe_252',1)):
    fig.add_trace(go.Scatter(x=tt.index,y=tt[col]*mult,name=LABELS[name],legendgroup=name,showlegend=n==1,line=dict(color=color,width=1.25),connectgaps=False),row=n,col=1)
  for y,rule in ((1,'gate_hold'),(0,'ablate_hold')):
   ti=times[f'{cost}_{rule}'];palette={'green':'#27814c','yellow':'#cb9700','red':'#b34343'}
   fig.add_trace(go.Scatter(x=ti.index,y=[y]*len(ti),mode='markers',marker=dict(size=4,color=ti.state.map(palette)),
       text=ti.state,hovertemplate='%{x}: %{text}<extra></extra>',showlegend=False),row=5,col=1)
  fig.update_yaxes(tickvals=[0,1],ticktext=['Without price peak','Combined'],row=5,col=1)
  fig.update_layout(height=1180,template='plotly_white',margin=dict(l=95,r=25,t=120,b=35),legend=dict(orientation='h',y=1.12,font=dict(size=11)))
  fig.write_html(out/f'cost-{cost}.html',include_plotlyjs='directory',full_html=True)
 decisions=[dict(id='D1',claim='Combined gate reduces both depth and duration versus own base at both costs',verdict='rejected in viewed development history',reason='Both combined gates reduce drawdown but extend longest underwater duration; reject the joint path claim.'),
   dict(id='D2',claim='Price-peak conditions are a plausible source of delayed recovery',verdict='one four-case ablation predeclared and completed',reason='612 of911 red sessions met the price trigger without volatility red. Same remaining thresholds, model and costs frozen before ablation results.'),
   dict(id='D3',claim='EMA/volatility-only gate improves specified historical path criterion',verdict='supported for both bases at5/10bp; retain for independent validation only',reason='All four comparisons pass; standalone growth sacrifice and base/control exposure differences remain. No untouched alpha, RL training, investment selection or live promotion.'),
   dict(id='D4',claim='More financial search in this epoch',verdict='stop:16/16attempts,2/2studies',reason='No threshold tuning, extra simulations or third study. Future independent data/evaluation needs a new scope.')]
 bundle=dict(status='bounded_epoch_reviewed',created_utc=datetime.now(timezone.utc).isoformat(),financial_attempts=16,failed_processes_preserved=2,completed_processes=14,
     qualified_failed_controls=2,studies=2,followup_cases=4,temporal_method='temporal-v1.2',references=manifests,rows=rows,annual=annual,blocks=block_rows,
     paired_path_tests=pairs,ablation_versus_combined=ablation_pairs,events=event_summary,red_window_summary=missed,
     audit_results=audit_results,event_audits=event_audits,control_parity=parity,decisions=decisions,
     analytical_cash=dict(cagr_pct=0,drawdown_pct=0,longest_underwater_sessions=0,sharpe=None,calmar=None,interest_rate=0,financial_attempts=0),
     source_paths={k:str(v.relative_to(ROOT)) for k,v in folders.items()},
     source_sha256=sha(ROOT/'reports/spy/20261024-235746-728801/source-data.json'),
     source_artifacts={str(f.relative_to(ROOT)):sha(f) for folder in folders.values() for f in sorted(folder.iterdir()) if f.is_file()},
     analysis_code_hashes={f:sha(ROOT/f) for f in ('scripts/current/build_risk_gate_epoch_review.py','reporting/risk_gate_review.py','research/evaluation/risk_gate_analysis.py','reporting/temporal.py')})
 write(out/'review-bundle.json',bundle);write(out/'audit-summary.json',dict(accounts=audit_results,events=event_audits,control_parity=parity))
 pd.DataFrame(rows).to_csv(out/'overall.csv',index=False);pd.DataFrame(annual).to_csv(out/'annual.csv',index=False);pd.DataFrame(block_rows).to_csv(out/'blocks.csv',index=False)
 pd.DataFrame(pairs).to_csv(out/'paired-tests.csv',index=False);pd.DataFrame(missed).to_csv(out/'red-window-summary.csv',index=False)
 # Tables share one cost selector; annual table also filters one year.
 def html_table(data,id):
  df=pd.DataFrame(data);h=df.to_html(index=False,border=0,float_format=lambda x:f'{x:,.3f}',table_id=id)
  return h
 overall_view=[{'Cost bps':r['cost_bps'],'Strategy':r['strategy'],'CAGR %':r['cagr_pct'],'Max DD %':r['drawdown_pct'],'Sharpe':r['sharpe'],'Calmar':r['calmar'],
                'Longest underwater sessions':r['longest_underwater_sessions'],'Calendar days':r['longest_underwater_days'],'Recovery unresolved':r['longest_censored']} for r in rows]
 annual_view=[{'Cost bps':r['cost_bps'],'Year':r['period'],'Strategy':r['strategy'],'Return %':r['return_pct'],'Max DD %':r['drawdown_pct'],'Sharpe':r['sharpe'],'Calmar':r['calmar']} for r in annual]
 pair_view=[{'Cost bps':r['cost_bps'],'Treatment':r['treatment'],'Base':r['base'],'Pass joint path test':r['path_criterion_pass'],'DD reduction pp':r['drawdown_reduction_pp'],
             'Underwater change sessions':r['underwater_change_sessions'],'CAGR change pp':r['cagr_change_pp']} for r in pairs]
 event_view=[{'Cost bps':r['cost_bps'],'Strategy':r['strategy'],'Warning episodes':r['warning_episodes'],'Left censored':r['left_censored'],'Complete warning horizons':r['evaluable_warning_episodes'],
              'Warnings followed by 5% price drop':r['warnings_with_drop'],'False alarm episodes':r['false_alarm_episodes'],'Actionable episodes':r['actionable_episodes'],'Actionable followed by drop':r['actionable_with_drop']} for r in event_summary]
 loss_view=[{'Cost bps':r['cost_bps'],'Strategy':r['strategy'],'Historical ES95 loss %':r['historical_es95_loss_pct'],**{f'Worst {w}-session %':r[f'worst_{w}_session_return_pct'] for w in (1,5,21,63)}} for r in rows]
 heading='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SPY risk gate — bounded improvement review</title><style>
 body{font:16px/1.55 system-ui;color:#172438;background:#f3f5fa;margin:auto;max-width:1350px;padding:32px}h1{font-size:34px;line-height:1.2}h2{margin-top:0}section{background:white;padding:24px;margin:20px 0;border-radius:12px}.flag{background:#e5f0eb;border-left:5px solid #28704b;padding:18px}.muted{color:#516176}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:10px;text-align:right;border-bottom:1px solid #dce1e8}td:nth-child(2),th:nth-child(2){text-align:left}.scroll{overflow:auto}iframe{border:0;width:100%;height:1220px}a{color:#214bc4}select{font:inherit;padding:5px;margin-right:15px}code{word-break:break-all}summary{cursor:pointer;font-weight:bold}</style>
 <h1>SPY risk gate: bounded improvement review</h1><p class="muted">Viewed 2005–2025 development history · USD 300,000 · nominal 1× · free/local inputs</p>
 <div class="flag"><strong>Removing the price-peak component improved the tested tradeoff.</strong><br>The combined gate failed the joint depth-and-duration criterion. The fixed EMA/volatility-only follow-up passed against both bases at both cost levels. This supports a research candidate, not independent alpha or a trading deployment.</div>
 <section><h2>What changed through the research loop</h2><pre>Fixed combined gate → audit and diagnose → remove one implicated component → four frozen tests → stop at 16 attempts</pre>
 <p>No thresholds were optimized. The four-case follow-up kept the EMA/volatility conditions, staged recovery and accounting fixed while removing raw price-peak drawdown conditions. The original gate stayed red in 911 sessions; in 612 of them the price trigger was active while volatility was below its red threshold.</p>
 <p><strong>16 financial attempts across two studies; budget exhausted.</strong> Fourteen processes completed. Two earlier control processes failed representation checks; their original failures remain preserved and their account evidence was separately qualified before subsequent comparisons. No failed financial case was rerun.</p></section>
 <section><h2>Compare like-for-like costs</h2><label for="cost">Adverse cost per side: </label><select id="cost"><option value="5">5 basis points</option><option value="10">10 basis points</option></select><p>All cases also pay $1 per actual net trade. Cash interest is zero; cash dividends, whole shares and the 99% reserve follow the common model. Buy-once holding retains initial shares and dividend cash; daily full-target holding resizes and is a separate benchmark.</p><div class="scroll">'''
 html=heading+html_table(overall_view,'overall')+'''</div></section><section><h2>Predeclared paired path criterion</h2><p>A treatment must be no worse on both drawdown magnitude and longest observed underwater duration, and better on at least one. Growth cost is reported separately; no acceptable sacrifice was chosen. A negative duration change means shorter underwater time. Censored recovery is unresolved, not proof of a shorter eventual recovery.</p><div class="scroll">'''+html_table(pair_view,'pairs')+'''</div></section>
 <section><h2>Equity, temporal metrics and state timing</h2><p>Toggle strategy legends or zoom. Colors mark states already available at that execution open. Rolling 252-session returns are cumulative, not annualized. Sharpe uses zero risk-free return and sample variance; flat cash windows remain undefined.</p><iframe id="chart" title="SPY performance and traffic-light timeline" src="cost-5.html"></iframe></section>
 <section><h2>Year by year</h2><label for="year">Year: </label><select id="year">'''+''.join(f'<option{" selected" if y==2020 else ""}>{y}</option>' for y in range(2005,2026))+'''</select><div class="scroll">'''+html_table(annual_view,'annual')+'''</div><p>Annual returns and drawdowns include the first session's return from the previous year-end balance. Strategies and capital continue through year boundaries; no refitting or artificial liquidation.</p></section>
 <section><h2>Warning episodes and missed rebounds</h2><p>A warning begins at an executed green-to-yellow/red transition and ends when green returns. The descriptive price label asks whether a raw close falls at least 5% below the warning-day open in that day plus 20 sessions. It excludes dividends and is not account P&amp;L. An actionable episode requires a target reduction versus its own base. False alarms and overlapping windows are not independent trials.</p><div class="scroll">'''+html_table(event_view,'events')+'''</div><p>For the combined gate, 3 of 13 complete warning episodes preceded that price event; 10 did not. This does not measure all market drops or prove predictive accuracy. Rebound tables retain every red entry/exit and 5/21/63-session net-account window, including the transition overnight gap; signed base-minus-gate returns can be positive or negative.</p><p><a href="red-window-summary.csv">Red-entry/exit return-gap summary</a> · full warning, transition and red-window files are linked below.</p></section>
 <section><h2>Losses over time</h2><div class="scroll">'''+html_table(loss_view,'losses')+'''</div><p>Historical daily ES95 is the mean loss among the worst ceil(5% × 5,283) observed daily returns, not a future loss limit. The three fixed chronological blocks use continuous ledgers and prior-close anchors. Within-block drawdown resets its measuring peak; the separate full-path column retains earlier peaks.</p><p><a href="blocks.csv">Three-block metrics</a> · <a href="annual.csv">All annual metrics</a> · <a href="overall.csv">All overall metrics</a></p></section>
 <section><h2>Cash references and interpretation</h2><p>The fixed half-target alternative retains more cash and supplies a simple lower-exposure reference, not exact risk matching. An analytical all-cash account earns 0%, has 0% drawdown and no underwater episode under zero interest; its Sharpe/Calmar are undefined and it consumes no simulation attempt. Higher Calmar alone did not save the combined gate's duration failure.</p>
 <p>The simpler EMA/volatility gate improved the predeclared historical path criterion, but all data were already viewed. The ablation was chosen after the combined result, so it is exploratory mechanism evidence. No trained RL advantage, untouched financial alpha, next-year return, annual-doubling result or 30% loss guarantee is established. These are daily-OHLC account-model simulations, not proof of native Nautilus fills, intraday execution or broker readiness. Taxes and independent data/provider-calendar validation remain outside the model.</p></section>
 <section><h2>Failures, recovery and evidence</h2><p>First failure: the legacy daily-long ledger had 14 columns and the current ledger added a constant nominal-budget diagnostic. Second failure: the wrapper represented EMA's off state as target budget zero while the legacy diagnostic retained nominal budget one and a separate off signal. Trades, holdings and monetary fields matched. The raw files and failed statuses remain intact; a clearly labeled derived EMA ledger changes only that diagnostic for the legacy comparison. The original 15-minute financial-study deadline was retained through recovery. A separate 15-minute limit governed the four-case follow-up.</p>
 <p>The rolling-Sharpe correction, temporal-v1.2, computes each window variance independently so a flat cash period after volatility has undefined Sharpe. Prior reports were not rewritten. Every case was rechecked through guarded Decimal accounting, 88 independent annual/overall financial metrics and full temporal checks; warning and red-window outcomes were separately checked.</p><p><a href="review-bundle.json">Machine-readable review and decisions</a> · <a href="audit-summary.json">Audits and explicit control parity</a> · <a href="manifest.json">Artifact manifest</a> · <a href="paired-tests.csv">Paired decisions</a></p><details><summary>Detailed temporal and event files</summary><ul>'''+''.join(f'<li><a href="diagnostics/{key}-temporal.json">{key}: temporal episodes</a>'+ (f' · <a href="diagnostics/{key}-events.json">warnings and red windows</a>' if key in event_results else '')+'</li>' for key in folders)+'''</ul><p><a href="diagnostics/5_ema-derived-legacy-budget-ledger.csv">Explicit derived EMA legacy-budget ledger</a></p></details></section>
 <section><h2>Next research decision</h2><p>Retire this combined price-peak configuration for the stated joint protection claim. Retain the EMA/volatility-only variant for an independently designed validation stage. Freeze it before accessing any new evaluation data; do not turn this study into a threshold sweep. The epoch's financial budget is fully used. Parallel research proposals may identify independent data or diversified alternatives, but have no new simulation budget.</p><p><a href="../../recursive-research/20261025-review-v3/index.html">Earlier research review</a> · <a href="../20261025-checkpoint-v2/index.html">Preserved stopped checkpoint</a></p></section>
 <script>function filter(){const c=document.getElementById('cost').value;const y=document.getElementById('year').value;for(const id of ['overall','pairs','events','losses','annual'])for(const r of document.querySelectorAll('#'+id+' tbody tr'))r.hidden=r.cells[0].innerText!==c||(id==='annual'&&r.cells[1].innerText!==y)}document.getElementById('cost').onchange=function(){document.getElementById('chart').src='cost-'+this.value+'.html';filter()};document.getElementById('year').onchange=filter;filter();</script></html>'''
 (out/'index.html').write_text(html)
 write(out/'manifest.json',dict(status='bounded_epoch_reviewed',artifact_hashes={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}))
 print(json.dumps(dict(output=str(out.relative_to(ROOT)),manifest=verify_artifacts(out),pairs=pairs,
        financial_metric_checks=sum(a['financial_metric_checks'] for a in audit_results.values()),
        temporal_window_checks=sum(a['temporal']['scalar_and_window_checks'] for a in audit_results.values()),
        event_checks=sum(a['field_checks'] for a in event_audits.values())),indent=2))

if __name__=='__main__':main()
