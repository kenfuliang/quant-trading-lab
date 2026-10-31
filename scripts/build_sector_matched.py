"""Audit and present fixed sector-only versus target-exposure-matched cases."""
import csv,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'.local/sector-matched-v1';OUT=ROOT/'.local/performance/sector-matched-v1'
NAMES={'original':'Original momentum','sector':'Sector-capped momentum','matched':'Target-exposure-matched control'}
SECTORS={101:'Basic materials',102:'Consumer cyclical',103:'Financial services',104:'Real estate',205:'Consumer defensive',206:'Healthcare',207:'Utilities',308:'Communication services',309:'Energy',310:'Industrials',311:'Technology'}
def assemble():
 ledger=json.loads((RAW/'attempts.json').read_text());plan=json.loads((ROOT/'research/plans/sector-matched-v1.json').read_text())
 packets={c:json.loads((RAW/f'{c}-packet.json').read_text()) for c in NAMES}
 baseline=json.loads((ROOT/'.local/stock-risk-v1/original-packet.json').read_text())
 registry=json.loads((ROOT/'research/plans/sector-matched-v1.classifications.json').read_text())
 runs=[];annual=[];months=[];contributions=[]
 missing={(r[0],r[1]) for r in json.loads((RAW/'probe-packet.json').read_text())['rows']}
 for c,p in packets.items():
  f=p['full'];assert f['n']==1508 and len(p['months'])==72 and p['resolved_n']==27 and p['selected_unknown_sector']==0
  assert abs(p['residual_usd'])<=.1
  assert abs(f['end']-10000-sum(a[1]/100 for a in p['contributions'])+f['financing_usd'])<=.1
  assert not any(f[k] for k in ('rejects','other_fills','pending_orders','feature_future','feature_invalid','feature_unordered','funding_debit_error'))
  assert math.isclose(f['calmar'],f['cagr']/abs(f['dd']),abs_tol=1e-8)
  rows=[dict(zip(p['annual_keys'],r),case=c) for r in p['annual']];assert [r['year'] for r in rows]==[str(y) for y in range(2020,2026)]
  assert sum(r['n'] for r in rows)==1508 and sum(r['global_uw'] for r in rows)==f['uw']
  wealth=10000
  for r in rows:
   wealth*=1+r['ret'];assert abs(wealth-r['end'])<.0001
   assert math.isclose(r['annual_calmar'],r['ret']/abs(r['dd']),abs_tol=1e-8)
  if c=='original':
   for k in ('end','cagr','dd','sharpe','calmar','uw','longest_uw','fees','fills'):
    assert math.isclose(f[k],baseline['full'][k],abs_tol=1e-7),(k,f[k],baseline['full'][k])
  attempts=[a for a in ledger['attempts'] if a['case']==c and a['status']=='completed-verified'];assert len(attempts)==1
  assert hashlib.sha256((RAW/f'{c}-source.py').read_bytes()).hexdigest()==attempts[0]['source_sha256']==plan['source_hashes'][c]
  runs.append(dict(f,case=c,name=NAMES[c],backtest_id=attempts[0]['backtest_id'],average_gross=p['average_gross'],peak_sector_gross=p['peak_sector_gross'],resolved_observations=p['resolved_n'],target_sha256=p['target_sha256']))
  annual+=rows
  reconstructed_hash=hashlib.sha256()
  for when,color,ready,indices in p['months']:
   date=f'{str(when)[:4]}-{str(when)[4:6]}-{str(when)[6:]}'
   chosen=[p['symbols'][i] for i in indices];totals={}
   for sid,sector in chosen:totals[sector]=totals.get(sector,0)+1
   targets=[.18*min(1,.36/(.18*totals[sector])) for sid,sector in chosen];total=sum(targets)
   effective=[.18]*5 if c=='original' else targets if c=='sector' else [total/5]*5
   reconstructed_hash.update(('%s:%.10f\n' % (date,sum(effective))).encode())
   for rank,((sid,sector),target) in enumerate(zip(chosen,effective),1):
    fallbacks=[r for r in registry['rows'] if r['sid']==sid and r['available_date']<date and r['effective_from']<=date<=r['effective_to']]
    months.append(dict(case=c,date=date,rank=rank,security_id=sid,sector_code=sector,sector=SECTORS[sector],eligible=ready,target=target,source='dated research fallback' if (date,sid) in missing else 'native sector'))
  assert reconstructed_hash.hexdigest()==p['target_sha256'],c
  assert len([r for r in months if r['case']==c and r['source']=='dated research fallback'])==27
  for i,pnl,fee in p['contributions']:
   sid,sector=p['symbols'][i];contributions.append(dict(case=c,security_id=sid,sector=SECTORS[sector],pnl_usd=pnl/100,fees_usd=fee/100))
 for key in ('calendar_hash','membership_sha256','feature_sha256'):
  assert len({p['full'][key] for p in packets.values()})==1
 assert len({p['gate_input_sha256'] for p in packets.values()})==1
 def signature(p):return [(m[0],m[2],[p['symbols'][i] for i in m[3]]) for m in p['months']]
 assert all(signature(p)==signature(packets['original']) for p in packets.values())
 assert packets['sector']['target_sha256']==packets['matched']['target_sha256']
 assert len(months)==1080 and len(annual)==18
 delta={k:packets['sector']['full'][k]-packets['matched']['full'][k] for k in ('cagr','dd','sharpe','calmar','longest_uw','end')}
 return dict(study='sector-matched-v1',status='complete-conditional-development',runs=runs,annual=annual,monthly_selections=months,contributions=contributions,classification_registry=registry,classification_audit=json.loads((RAW/'classification-audit.json').read_text()),sector_minus_matched=delta,attempts=ledger['attempts'],checks=['Fresh original financial control reproduces prior results','Identical 1,508 sessions, 72 monthly stock selections, universe and feature hashes','Sector and matched monthly total target hashes identical','All 27 missing observations resolved with strictly earlier dated evidence','Native PnL/financing residual within 10 cents; annual compounding and Calmar checked','No rejected, non-MOO, pending orders or invalid features'],limits=plan['limits']+['Four issuer labels are conditional public-filing research inferences, not recovered historical Morningstar truth','Target exposure matched at monthly decisions; realized gross exposure differs through returns, fees, rounding and staged fills','36% NAV sector target cap is not a continuous holding limit','Native net PnL includes fees; not independent fill/cash reconstruction or causal factor attribution','Daily Sharpe moments/raw NAV not exported; Sharpe is not independently reconstructed','Vendor history remains hosted and can change; derived hashes audit observed inputs','Market traffic-light gate is observed but never applied in any of these three cases','Security IDs can retain old ticker prefixes; only four missing issuers have decision-date ticker verification'])
def build():
 d=assemble();OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'comparison.json').write_text(json.dumps(d,indent=2)+'\n')
 for file,key in [('annual','annual'),('monthly-selections','monthly_selections'),('stock-contributions','contributions')]:
  with (OUT/f'{file}.csv').open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(d[key][0]));w.writeheader();w.writerows(d[key])
 html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Sector limits: allocation or cash?</title>
<style>body{font:15px system-ui;color:#23343c;background:#f6f4ed;margin:30px;max-width:1600px}h1{font-size:30px}h2{margin-top:30px}p{max-width:1150px;line-height:1.6}.note{padding:16px;background:#fff0cb;border-radius:9px}table{border-collapse:collapse;background:white;width:100%;font-variant-numeric:tabular-nums}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#e0e9e2}select,input{padding:8px;margin:8px}.scroll{overflow:auto}a{color:#246e77}</style>
<h1>Sector limits: allocation benefit or simply more cash?</h1>
<p>Three fixed cases · 2020–2025 · $10,000 · whole shares · 25bp slippage · native IB fees · 6% debit financing · same monthly top five.</p>
<p class="note"><b>Conditional development evidence.</b> All 27 missing selection observations received dated public-filing research classifications. These are inferred labels, not recovered historical Morningstar truth. No traffic-light gate is applied. Matching is monthly target exposure; actual holdings drift.</p>
<h2>Full-period comparison</h2><div class="scroll"><table id="full"></table></div><p id="verdict"></p>
<h2>Year by year</h2><select id="year"></select><div class="scroll"><table id="annual"></table></div>
<h2>Monthly top five and intended allocations</h2><p>Sector cap 36% NAV with residual cash. The matched control spreads the same total target equally across the original five. Neither treatment replaces stocks.</p><select id="case"></select><select id="month"></select><div class="scroll"><table id="monthly"></table></div>
<h2>Every security’s full-period contribution</h2><p>Native net P&amp;L includes fees and remaining open holdings. Do not subtract disclosed fees again. Security IDs may retain older ticker prefixes.</p><input id="search" placeholder="Find security"><div class="scroll"><table id="stocks"></table></div>
<h2>Historical classification fallback registry</h2><p>Business-to-sector mapping is an explicit research assumption. Availability must precede the decision, with a maximum 365 calendar-day source life. Full sources and rationale are in the evidence JSON.</p><div class="scroll"><table id="registry"></table></div>
<p><a href="annual.csv">Annual CSV</a> · <a href="monthly-selections.csv">Monthly decisions CSV</a> · <a href="stock-contributions.csv">Contributions CSV</a> · <a href="comparison.json">Evidence and sources</a> · <a href="manifest.json">Artifact hashes</a></p><h2>Checks and limitations</h2><ul id="checks"></ul><ul id="limits"></ul>
<script>const D=DATA;const $=id=>document.getElementById(id);const pct=x=>(100*x).toFixed(2)+'%';const num=x=>x.toFixed(2);const usd=x=>'$'+x.toLocaleString('en-US',{maximumFractionDigits:2,minimumFractionDigits:2});const names=Object.fromEntries(D.runs.map(r=>[r.case,r.name]));function table(id,heads,rows){$(id).replaceChildren();for(const [i,row] of [heads,...rows].entries()){let tr=document.createElement('tr');for(const v of row){let td=document.createElement(i?'td':'th');td.textContent=v;tr.append(td)}$(id).append(tr)}}
table('full',['Case','CAGR','Max drawdown','Sharpe','Calmar','Longest underwater sessions / days','Underwater fraction','Unrecovered at end','Average gross','Peak sector gross','End equity'],D.runs.map(r=>[r.name,pct(r.cagr),pct(-r.dd),num(r.sharpe),num(r.calmar),r.longest_uw+' / '+r.longest_uw_days,pct(r.uw_fraction),r.censored?'Yes':'No',pct(r.average_gross),pct(r.peak_sector_gross),usd(r.end)]));let delta=D.sector_minus_matched;$('verdict').textContent='Primary comparison, sector minus matched: Calmar '+num(delta.calmar)+'; CAGR '+(100*delta.cagr).toFixed(2)+' percentage points; longest underwater '+delta.longest_uw+' sessions. Target hashes match exactly; actual gross differs.';
for(let y=2020;y<=2025;y++)$('year').add(new Option(y,y));for(const r of D.runs)$('case').add(new Option(r.name,r.case));for(const m of [...new Set(D.monthly_selections.map(r=>r.date))])$('month').add(new Option(m,m));
function annual(){table('annual',['Case','Return','Annual-reset DD','Sharpe','Calmar','Longest underwater sessions','Underwater sessions','Unrecovered at year-end'],D.annual.filter(r=>r.year===$('year').value).map(r=>[names[r.case],pct(r.ret),pct(-r.dd),num(r.sharpe),num(r.annual_calmar),r.longest_uw,r.uw,r.censored?'Yes':'No']))}function detail(){let c=$('case').value;table('monthly',['Rank','Security ID','Resolved sector','Classification source','Eligible','Target'],D.monthly_selections.filter(r=>r.case===c&&r.date===$('month').value).map(r=>[r.rank,r.security_id,r.sector,r.source,r.eligible,pct(r.target)]));table('stocks',['Security ID','Last observed sector','Net P&L','Fees included'],D.contributions.filter(r=>r.case===c&&r.security_id.toLowerCase().includes($('search').value.toLowerCase())).sort((a,b)=>b.pnl_usd-a.pnl_usd).map(r=>[r.security_id,r.sector,usd(r.pnl_usd),usd(r.fees_usd)]))}
$('year').onchange=annual;$('case').onchange=detail;$('month').onchange=detail;$('search').oninput=detail;annual();detail();table('registry',['Security ID','Display ticker','Sector code','Source ID','Available','Effective through'],D.classification_registry.rows.map(r=>[r.sid,r.display_ticker,r.sector,r.source_id,r.available_date,r.effective_to]));for(const k of ['checks','limits'])for(const s of D[k]){let li=document.createElement('li');li.textContent=s;$(k).append(li)};</script></html>'''.replace('DATA',json.dumps(d,separators=(',',':')).replace('</','<\\/'))
 (OUT/'index.html').write_text(html)
 manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.name!='manifest.json'}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 evidence={k:d[k] for k in ('study','status','attempts','checks','limits','sector_minus_matched')};evidence.update(artifacts=manifest,source_hashes=json.loads((ROOT/'research/plans/sector-matched-v1.json').read_text())['source_hashes'])
 (ROOT/'docs/tasks/evidence/2026-10-26-sector-matched.json').write_text(json.dumps(evidence,indent=2)+'\n')
 print([(r['case'],r['cagr'],r['dd'],r['calmar'],r['longest_uw']) for r in d['runs']]);print('Annual',len(d['annual']),'selections',len(d['monthly_selections']),'contributions',len(d['contributions']))
if __name__=='__main__':build()
