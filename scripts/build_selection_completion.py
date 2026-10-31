"""Validate and display saved aggregate bounded-selection research evidence."""
import csv,hashlib,json,math,sys
from datetime import date
from pathlib import Path
from build_qc_breadth import validate as baseline_validate
from prepare_selection_completion import CASES
from parse_selection_completion_fragments import decode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));RAW=ROOT/'.local/selection-completion-v1';OUT=ROOT/'.local/performance/selection-completion-v1'
NAMES=dict(asset='ETF momentum',stock='Stock momentum',lowvol='Low-volatility stocks',spy='SPY holding',ew_asset='Equal-weight ETFs (5)',ew_stock='Equal-weight stock universe',ew_low='Equal-weight low-vol universe',stress='Stock momentum · 50 bp + delay',ew_stress='Equal-weight stocks · 50 bp + delay',t11='T11 reference')
def read_case(case):
 saved=json.loads((RAW/f'{case}-summary-cells.json').read_text())
 decoded=decode(json.loads((RAW/f'{case}-terminal-fragments.json').read_text()),case)
 if saved!=decoded:raise ValueError('Decoded source summary mismatch')
 rows=[json.loads(x) for x in saved]
 if any(r.get('study')!='selection-completion-v1' or r.get('case')!=case for r in rows):raise ValueError('Study/case identity mismatch')
 # Reuse tested arithmetic checker without changing immutable source summaries.
 converted=[dict(r,study='qc-breadth-v1') for r in rows];full,ys=baseline_validate(converted,case)
 full['study']='selection-completion-v1'
 for y in ys:y['study']='selection-completion-v1'
 full['attribution']=next(r for r in rows if r['kind']=='assets')
 return full,ys

def build():
 from research.us_etf_calendar import sessions
 calendar=sessions('2020-01-01','2025-12-31');expected_hash=hashlib.sha256(''.join(x.strftime('%Y-%m-%d')+'\n' for x in calendar).encode()).hexdigest()
 plan=json.loads((ROOT/'research/plans/selection-completion-v1.json').read_text());ledger=json.loads((RAW/'attempts.json').read_text());runs=[];annual=[];engines={}
 for c in CASES:
  success=[a for a in ledger['attempts'] if a['case']==c and a['status']=='completed-verified']
  if len(success)!=1:raise ValueError('Missing unique verified attempt: '+c)
  if hashlib.sha256((RAW/f'{c}-source.py').read_bytes()).hexdigest()!=plan['source_hashes'][c] or success[0]['source_sha256']!=plan['source_hashes'][c]:raise ValueError('Source identity failure')
  engines[c]=json.loads((RAW/f'{c}-engine-evidence.json').read_text())
  if len(engines[c])!=2 or 'LEAN Engine v2.5.0.0.18209' not in engines[c][0] or 'completed in' not in engines[c][1]:raise ValueError('Engine identity failure')
  f,ys=read_case(c)
  if f['n']!=len(calendar) or f['calendar_hash']!=expected_hash or f['first']!='2020-01-02' or f['last']!='2025-12-31':raise ValueError('Calendar failure')
  if any(y['n']!=sum(calendar.year==int(y['year'])) for y in ys):raise ValueError('Annual calendar mismatch')
  if f['feature_future'] or f['feature_invalid'] or f['feature_unordered']:raise ValueError('Causal feature failure')
  if c!='spy' and (f['selection_events']!=72 or f['min_ready']<=0):raise ValueError('Readiness correction not observed')
  if c in ('asset','ew_asset') and (f['min_ready']!=5 or f['history_short']):raise ValueError('ETF readiness correction failed')
  expected_cagr=(f['end']/10000)**(365.25/(date(2025,12,31)-date(2019,12,31)).days)-1
  if not math.isclose(expected_cagr,f['cagr'],abs_tol=1e-10) or not math.isclose(f['end']/10000-1,f['ret'],abs_tol=1e-10):raise ValueError('Full return/CAGR mismatch')
  if not math.isclose(f['uw']/f['n'],f['uw_fraction'],abs_tol=1e-10) or not 0<=f['longest_uw']<=f['uw']<=f['n']:raise ValueError('Full underwater inconsistency')
  if any(y['dd']<f['dd']-1e-8 or not 0<=y['longest_uw']<=y['uw']<=y['global_uw']<=y['n'] or y['longest_uw']>f['longest_uw'] for y in ys):raise ValueError('Annual/global drawdown or underwater inconsistency')
  for y in ys:
   n=y['n'];m=y['return_sum'];sq=y['return_square_sum'];sd=math.sqrt(max(0,(sq-m*m/n)/(n-1)))
   if sd>1e-15 and not math.isclose(m/n/sd*math.sqrt(252),y['sharpe'],abs_tol=1e-5):raise ValueError('Annual Sharpe mismatch')
  if f['rejects'] or f['other_fills'] or f['pending_orders'] or f['fills']<=0:raise ValueError('Execution failure')
  if not math.isclose(sum(y['return_sum'] for y in ys),f['return_sum'],abs_tol=1e-7) or not math.isclose(sum(y['return_square_sum'] for y in ys),f['return_square_sum'],abs_tol=1e-7):raise ValueError('Annual/full return moments disagree')
  if not math.isclose(sum(y['financing_usd'] for y in ys),f['financing_usd'],abs_tol=1e-8) or f['funding_debit_error']>1e-4:raise ValueError('Funding failure')
  if abs(f['pnl_residual_usd'])>2:raise ValueError('PnL reconciliation failure')
  f['context']='stress' if c in ('stress','ew_stress') else 'base';f['cached']=False
  runs.append(f);annual+=ys
 by={r['case']:r for r in runs}
 for a,b in [('asset','ew_asset'),('stock','ew_stock'),('lowvol','ew_low'),('stress','ew_stress')]:
  for k in ('membership_sha256','feature_sha256','history_short','selection_events'):
   if by[a][k]!=by[b][k]:raise ValueError('Matched inputs differ '+a+' '+b+' '+k)
 prior_file=ROOT/'.local/performance/qc-breadth-v1/comparison.json'
 if hashlib.sha256(prior_file.read_bytes()).hexdigest()!=plan['baseline']['qc-breadth-v1']['comparison_sha256']:raise ValueError('Cached comparison drift')
 prior=json.loads(prior_file.read_text())
 cached_engine=prior['evidence']['engine_evidence']['t11']
 if len(cached_engine)!=2 or 'LEAN Engine v2.5.0.0.18209' not in cached_engine[0] or 'completed in' not in cached_engine[1]:raise ValueError('Cached engine mismatch')
 t11=next(r for r in prior['runs'] if r['case']=='t11');t11=dict(t11,cached=True,context='base');runs.append(t11);annual += [dict(y,cached=True) for y in prior['annual'] if y['case']=='t11']
 if len({r['calendar_hash'] for r in runs})!=1:raise ValueError('Session calendars differ')
 for k in ('end','cagr','dd','sharpe','calmar','fills','fees','financing_usd'):
  if not math.isclose(by['spy'][k],next(r for r in prior['runs'] if r['case']=='spy')[k],abs_tol=1e-8):raise ValueError('SPY control drift '+k)
 decisions=[]
 for a,b,kind in [('asset','ew_asset','growth'),('stock','ew_stock','growth'),('lowvol','ew_low','risk')]:
  x,y=by[a],by[b];passed=x['cagr']>y['cagr'] if kind=='growth' else x['dd']>y['dd'] and x['cagr']>=0
  decisions.append(dict(case=a,control=b,mechanism_passed=passed,disposition='retain for independent validation' if passed else 'stop this fixed variant',cagr_difference=x['cagr']-y['cagr'],drawdown_depth_difference=abs(x['dd'])-abs(y['dd']),longest_underwater_difference=x['longest_uw']-y['longest_uw']))
 evidence=dict(study='selection-completion-v1',status='financial-summaries-audited',calendar_check=dict(sessions=len(calendar),sha256=expected_hash,fixture='research/us_etf_calendar.py; independently derived research calendar, not venue certification'),plan=plan,attempts=ledger,engine_evidence=engines,decisions=decisions,checks=['Checksummed source summaries','1508 identical sessions','Annual NAV compounding and return moments','Calmar and annual/full Sharpe reconciliation','Matched historical membership and eligible-feature hashes','No invalid orders/non-MOO fills/open orders','SPY reproduced prior control','Cached T11 baseline manifest previously verified'],limits=['Viewed development years, no independent alpha','USD10000 whole-share account; USD 300,000 capacity untested','Daily closing drawdown does not bound intraday loss','Hosted adjusted inputs not independently archived; underlying publication and adjustment integrity remain provider-dependent','Native PnL residual is not an independent cash/fill reconstruction','Low-vol daily and momentum monthly universes differ','Stress combines cost and delay; neither is independently identified'])
 if (RAW/'final-validation.json').exists():evidence.update(final_validation=json.loads((RAW/'final-validation.json').read_text()),status='complete-scoped-research' if ledger['status']=='closed' else evidence['status'])
 evidence['diagnostic_result']=json.loads((RAW/'diagnosis.json').read_text())
 data=dict(names=NAMES,runs=runs,annual=annual,decisions=decisions,evidence=evidence);OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
 with (OUT/'annual.csv').open('w') as fp:
  w=csv.DictWriter(fp,fieldnames=['case','year','ret','dd','sharpe','annual_calmar','global_uw','n','longest_uw','financing_usd','end'],extrasaction='ignore');w.writeheader();w.writerows(annual)
 (OUT/'index.html').write_text(PAGE.replace('PAYLOAD',json.dumps(data).replace('</','<\\/')))
 (ROOT/'docs/tasks/evidence/2026-10-26-selection-completion.json').write_text(json.dumps(evidence,indent=2)+'\n')
 (OUT/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n')
 print(json.dumps(dict(decisions=decisions,runs=[{k:r[k] for k in ('case','cagr','dd','sharpe','calmar','longest_uw','min_ready','history_short') if k in r} for r in runs]),indent=2))
PAGE='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Selection research · bounded review</title><style>
body{background:#f5f3eb;color:#202e37;font:16px system-ui;margin:40px auto;padding:0 26px;max-width:1500px}h1{font:48px Georgia;margin-bottom:12px}h2{font:28px Georgia}.eyebrow{letter-spacing:2px;font-size:12px;text-transform:uppercase;color:#496964}.card{background:#fffef8;border:1px solid #cbd0c4;border-radius:12px;padding:20px;margin:20px 0}.warn{border-left:5px solid #bb893b;padding:14px;background:#fff0d5}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{text-align:right;padding:12px 9px;border-bottom:1px solid #d6dacd;white-space:nowrap}td:first-child,th:first-child{text-align:left}th{font-size:13px;color:#496964;white-space:normal;max-width:140px}td:first-child{white-space:normal;min-width:170px;max-width:240px}#attribution td:last-child{white-space:normal;min-width:280px;max-width:400px}select{font:inherit;padding:8px}.small{font-size:13px;color:#52615c}a{color:#21675c}.flow{font-family:monospace;padding:14px;border:1px dashed #79877d;border-radius:10px}button{padding:7px 12px;font:inherit}</style>
<div class="eyebrow">Research / selection-completion-v1 / development evidence</div><h1>What does asset selection add?</h1><p>Three fixed strategy adaptations, matched equal-weight controls, SPY and cached T11. January 2020–December 2025 · USD 10,000 · whole shares.</p>
<div class="flow">Verified history → eligible universe → ranking vs equal weight → staged next-open fills → costs → annual and temporal audit → lesson</div>
<p class="warn">These years were viewed before this experiment. Rankings describe these fixed variants; they do not establish financial alpha or deployment readiness. T11 is cached, with embedded leveraged ETF exposure and a different signal.</p>
<div class="card"><h2>Full-period comparison</h2><p>Base: 25 bp slippage + native IB fees; 90% target; 6% debit ACT/360, zero credit interest. Stress: 50 bp plus one extra observed-session delay, shown separately. SPY is an entry-only90% target; selection cases rebalance monthly. Actual exposure varies.</p><p class="small">UW means below a prior equity peak. Longest days run from peak to last underwater mark, excluding recovery day. Ending below the peak means recovery remains right-censored.</p><label>Rank by <select id="rank"><option value="calmar">Calmar</option><option value="sharpe">Sharpe</option><option value="cagr">CAGR</option></select></label><div class="scroll"><table id="full"></table></div></div>
<div class="card"><h2>Year by year</h2><label>Year <select id="year"></select></label><div class="scroll"><table id="annual"></table></div><p class="small">The rank selector also sorts annual rows within each cost context; CAGR selection uses annual return here. Annual drawdown resets at year opening NAV. Global underwater counts refer to the continuous prior peak; longest annual underwater stretch resets each year. Annual Calmar uses annual return; full Calmar uses CAGR.</p></div>
<div class="card"><h2>Decision cards</h2><div id="decisions"></div><p class="small">Retain means a candidate for independent validation, not live trading. ETF momentum has low research priority because its edge is small and recovery is slower. Stock stress drawdown is30.43%, beyond the approximate30% reassessment level. Nominal budget does not match realized exposure. The stress pair was selected after viewing stock momentum’s prior result.</p></div>
<div class="card"><h2>Data and execution evidence</h2><div class="scroll"><table id="inputs"></table></div><p>SPY holding has no selection-feature window; its readiness is not applicable. Feature windows require 253 positive finite closes with ordered unique timestamps ending at the current completed session. Wider 600 calendar-day requests repair the observed early-close count anomaly; short histories remain ineligible.</p><p class="small">Minimum cash and peak gross are extrema, not average exposure. Whole shares and minimum fees can disadvantage broad controls at this capital. Native PnL reconciliation is an engine consistency check, not independent fill/cash accounting. Daily closing drawdown omits intraday loss. Historical vendor inputs and USD 300,000 capacity remain independently unqualified.</p></div>
<div class="card"><h2>Where profits and losses accumulated</h2><p>Native per-security P&amp;L aggregates over the full period. These are accounting contributions, not causal attribution or standalone strategy returns. Extremes show two largest and two smallest contributions; omitted names remain in totals.</p><div class="scroll"><table id="attribution"></table></div></div><p><a href="comparison.json">Full evidence JSON</a> · <a href="annual.csv">Annual CSV</a> · <a href="manifest.json">Artifact hashes</a></p><script>const d=PAYLOAD;
const pp=x=>(x*100).toFixed(2)+' pp';const pct=x=>x==null?'—':(x*100).toFixed(2)+'%',num=x=>x==null?'—':x.toFixed(3);
const tr=(r,annual=false)=>`<tr><td>${d.names[r.case]}${r.cached?' [cached]':''}${['stress','ew_stress'].includes(r.case)?' [stress]':''}</td><td>${pct(annual?r.ret:r.cagr)}</td><td>${pct(-r.dd)}</td><td>${num(r.sharpe)}</td><td>${num(annual?r.annual_calmar:r.calmar)}</td><td>${r.longest_uw}</td><td>${annual?pct(r.global_uw/r.n):pct(r.uw_fraction)}</td><td>${annual?(r.censored?'Yes':'No'):r.longest_uw_days}</td>${annual?'':'<td>'+(r.censored?'Yes':'No')+'</td>'}</tr>`;
function full(){const k=document.getElementById('rank').value;document.getElementById('full').innerHTML='<tr><th>Case</th><th>CAGR</th><th>MaxDD depth</th><th>Sharpe</th><th>Calmar</th><th>Longest UW sessions</th><th>UW fraction</th><th>Longest UW days</th><th>Below prior peak at end</th></tr>'+['base','stress'].map(c=>d.runs.filter(r=>r.context===c).sort((a,b)=>b[k]-a[k]).map(r=>tr(r)).join('')).join('')}
function years(){document.getElementById('annual').innerHTML='<tr><th>Case</th><th>Annual return</th><th>Annual DD depth</th><th>Sharpe</th><th>Annual Calmar</th><th>Longest annual UW sessions</th><th>Global UW fraction</th><th>Still UW at year end</th></tr>'+d.annual.filter(r=>r.year===document.getElementById('year').value).sort((a,b)=>Number(['stress','ew_stress'].includes(a.case))-Number(['stress','ew_stress'].includes(b.case))||b[({calmar:'annual_calmar',sharpe:'sharpe',cagr:'ret'})[document.getElementById('rank').value]]-a[({calmar:'annual_calmar',sharpe:'sharpe',cagr:'ret'})[document.getElementById('rank').value]]).map(r=>tr(r,true)).join('')}
document.getElementById('year').innerHTML=[2020,2021,2022,2023,2024,2025].map(y=>`<option>${y}</option>`).join('');document.getElementById('year').onchange=years;document.getElementById('rank').onchange=()=>{full();years()};
document.getElementById('decisions').innerHTML=d.decisions.map(r=>`<p><strong>${d.names[r.case]}: ${r.disposition}.</strong> Net CAGR difference ${pp(r.cagr_difference)}; drawdown-depth difference ${pp(r.drawdown_depth_difference)}; longest underwater difference ${r.longest_underwater_difference} sessions versus ${d.names[r.control]}.</p>`).join('');
document.getElementById('inputs').innerHTML='<tr><th>Case</th><th>Min ready</th><th>Short histories</th><th>Fills</th><th>Rejected</th><th>Peak closing gross</th><th>Minimum cash USD</th><th>Cash clips</th><th>Fees USD</th><th>Financing USD</th><th>Native PnL residual USD</th></tr>'+d.runs.map(r=>`<tr><td>${d.names[r.case]}</td><td>${r.case==='spy'?'n/a':(r.min_ready??'—')}</td><td>${r.history_short??'—'}</td><td>${r.fills}</td><td>${r.rejects}</td><td>${pct(r.max_gross)}</td><td>${num(r.min_cash)}</td><td>${r.cash_clips??'—'}</td><td>${num(r.fees)}</td><td>${num(r.financing_usd)}</td><td>${num(r.pnl_residual_usd)}</td></tr>`).join('');document.getElementById('attribution').innerHTML='<tr><th>Case</th><th>Contributing names</th><th>Positive P&amp;L USD</th><th>Negative P&amp;L USD</th><th>Largest winner / positive P&amp;L</th><th>Extremes: name · P&amp;L USD</th></tr>'+d.runs.filter(r=>r.attribution).map(r=>`<tr><td>${d.names[r.case]}</td><td>${r.attribution.asset_count}</td><td>${num(r.attribution.positive_pnl)}</td><td>${num(r.attribution.negative_pnl)}</td><td>${pct(r.attribution.largest_gain_share)}</td><td>${r.attribution.values.map(v=>v[0].split(' ')[0]+' · '+v[1].toFixed(2)).join('; ')}</td></tr>`).join('');full();years();</script></html>'''
if __name__=='__main__':build()
