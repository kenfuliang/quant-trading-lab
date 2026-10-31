"""Audit saved derived packets and render the fixed five-case review; no simulation."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'.local/stock-risk-v1'
OUT=ROOT/'.local/performance/stock-risk-v1'
NAMES=dict(original='Original momentum',gate='Momentum + gate',sector='Momentum + sector limit',combined='Momentum + both',spy='SPY holding (90% initial target)')
SECTORS={0:'Unknown',101:'Basic materials',102:'Consumer cyclical',103:'Financial services',104:'Real estate',205:'Consumer defensive',206:'Healthcare',207:'Utilities',308:'Communication services',309:'Energy',310:'Industrials',311:'Technology'}


def assemble():
    ledger=json.loads((RAW/'attempts.json').read_text())
    plan=json.loads((ROOT/'research/plans/stock-risk-v1.json').read_text())
    baseline=json.loads((ROOT/'.local/performance/selection-completion-v1/comparison.json').read_text())
    packets={c:json.loads((RAW/f'{c}-packet.json').read_text()) for c in NAMES}
    runs=[];annual=[];months=[];contributions=[]
    for case,p in packets.items():
        f=p['full']; assets=p['contributions']
        assert f['n']==1508 and len(p['months'])==72
        assert abs(f['end']-10000-sum(v[1]/100 for v in assets)+f['financing_usd'])<=.1
        assert abs(p['residual_usd'])<=.1
        assert not any(f[k] for k in ('rejects','other_fills','pending_orders','feature_future','feature_invalid','feature_unordered'))
        assert abs(f['calmar']-f['cagr']/abs(f['dd']))<1e-8
        annual_rows=[dict(zip(p['annual_keys'],row),case=case) for row in p['annual']]
        assert [r['year'] for r in annual_rows]==[str(y) for y in range(2020,2026)]
        assert sum(r['n'] for r in annual_rows)==f['n']
        assert sum(p['gate_counts'].values())==f['n']
        wealth=10000
        for r in annual_rows:
            wealth*=1+r['ret']
            assert abs(wealth-r['end'])<.0001
            assert abs(r['annual_calmar']-r['ret']/abs(r['dd']))<1e-8
        # Annual-reset peaks differ from the continuous full-period peak.
        assert all(0 <= r['uw'] <= r['n'] for r in annual_rows)
        assert sum(r['global_uw'] for r in annual_rows)==f['uw']
        if case in ('original','spy'):
            old=next(r for r in baseline['runs'] if r['case']==('stock' if case=='original' else 'spy'))
            for k in ('end','cagr','dd','sharpe','calmar','uw','longest_uw','fees','fills'):
                assert math.isclose(f[k],old[k],abs_tol=1e-7), (case,k,f[k],old[k])
        attempts=[a for a in ledger['attempts'] if a['case']==case and a['status']=='completed-verified']
        assert len(attempts)==1
        assert hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()==attempts[0]['source_sha256']==plan['source_hashes'][case]
        runs.append(dict(f,case=case,name=NAMES[case],backtest_id=attempts[0]['backtest_id'],average_gross=p['average_gross'],peak_sector_gross=p['peak_sector_gross'],unknown_sector=p['selected_unknown_sector'],gate_counts=p['gate_counts'],gate_changes=p['gate_changes']))
        annual+=annual_rows
        seen=[]
        for when,color,ready,indices in p['months']:
            date=f'{str(when)[:4]}-{str(when)[4:6]}-{str(when)[6:]}'
            assert date not in seen;seen.append(date)
            chosen=[p['symbols'][i] for i in indices]
            totals={}
            for sid,sector in chosen:totals[sector]=totals.get(sector,0)+1
            for rank,(sid,sector) in enumerate(chosen,1):
                base=.9 if case=='spy' else .18
                limited=base
                if case in ('sector','combined'):
                    limited=base*min(1.,.36/(base*totals[sector])) if sector>0 else 0.
                multiplier=(0.,1.,.5,0.)[color] if case in ('gate','combined') else 1.
                months.append(dict(case=case,date=date,gate=('unassessed','green','yellow','red')[color],ready=ready,rank=rank,security_id=sid,sector_code=sector,sector='Benchmark (no sector look-through)' if case=='spy' else SECTORS.get(sector,str(sector)),base_target=base,sector_target=limited,effective_target=limited*multiplier))
        assert seen==sorted(seen) and len({s[:7] for s in seen})==72
        for index,pnl,fee in assets:
            sid,sector=p['symbols'][index]
            contributions.append(dict(case=case,security_id=sid,sector='Benchmark (no sector look-through)' if case=='spy' else SECTORS.get(sector,str(sector)),pnl_usd=pnl/100,fees_usd=fee/100))
    assert len({p['full']['calendar_hash'] for p in packets.values()})==1
    assert len({p['gate_input_sha256'] for p in packets.values()})==1
    for key in ('membership_sha256','feature_sha256'):
        assert len({packets[c]['full'][key] for c in ('original','gate','sector','combined')})==1
    def selection_signature(p):
        return [(m[0],m[2],[p['symbols'][i] for i in m[3]]) for m in p['months']]
    assert all(selection_signature(packets[c])==selection_signature(packets['original']) for c in ('gate','sector','combined'))
    assert len(annual)==30 and len(months)==1512
    result=dict(study='stock-risk-v1',status='complete-scoped-development',runs=runs,annual=annual,monthly_selections=months,contributions=contributions,attempts=ledger['attempts'],checks=['Fresh original/SPY financial parity','Identical stock universe/feature/selected-five identities','Identical1508session calendar and RAW gate inputs','Native PnL plus financing residual within10c','Annual compounding/Calmar/UW totals','No rejected/nonMOO/open orders or invalid features'],limits=plan['limits']+['Monthly targets are reconstructed from fixed rule; execution is staged','Monthly gate color is a snapshot; the gate also changes between months','Per-stock PnL is full-period native accounting; no monthly security PnL, causal or factor alpha attribution','Daily Sharpe moments not exported; native calculated metric is not independently reconstructed from raw NAV','Security IDs can retain old ticker prefixes; decision-date display ticker mapping was not exported','Hosted vendor snapshots are not independently frozen; hashes cover observed membership, eligibility and RAW gate inputs','Peak sector exposure uses latest observed monthly classification; SPY unknown bucket is not look-through sector exposure'])
    return result


def build():
    result=assemble();OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    for name,key in [('annual','annual'),('monthly-selections','monthly_selections'),('stock-contributions','contributions')]:
        rows=result[key]
        with (OUT/f'{name}.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    data=json.dumps(result,separators=(',',':')).replace('</','<\\/')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Stock momentum · risk controls</title>
<style>body{font:15px system-ui;background:#f6f4ed;color:#24343b;margin:32px;max-width:1600px}h1{font-size:30px}h2{margin-top:34px}p{max-width:1100px;line-height:1.6}.note{background:#fff2cc;padding:16px;border-radius:8px}table{border-collapse:collapse;background:white;width:100%;font-variant-numeric:tabular-nums}th,td{padding:10px 12px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#e3ebe6}select,input{padding:8px;margin:6px 16px 12px 0}a{color:#256b74}.scroll{overflow:auto}.green{color:#267346}.yellow{color:#997000}.red{color:#a43131}</style>
<h1>Stock momentum: what do risk controls change?</h1><p>Five fixed cases · 2020–2025 · $10,000 whole shares · 25bp slippage · native IB fees · 6% debit financing · 90% base target.</p>
<p class="note"><b>Development evidence.</b> Previously viewed history. Sector limit caps decision targets at36% before gate; weights drift and fills take time. Original/SPY controls must reproduce prior results. No live qualification.</p>
<h2>Full-period comparison</h2><div class="scroll"><table id="full"></table></div>
<h2>Year by year</h2><label>Year <select id="year"></select></label><div class="scroll"><table id="annual"></table></div>
<h2>Monthly selections and target decisions</h2><p>Same original top five in every stock case; sector treatment scales concentrated sectors and leaves residual cash. Targets shown are intentions, not immediate fills. Gate is evaluated daily; this table shows its monthly decision snapshot.</p>
<label>Case <select id="case"></select></label><label>Month <select id="month"></select></label><div class="scroll"><table id="monthly"></table></div>
<h2>Every stock’s full-period contribution</h2><p>Native accounting P&amp;L combines closed and remaining holdings. Fees are separately disclosed and already reflected in net contribution; do not subtract twice. Security identifiers distinguish mappings/corporate actions and can retain old ticker prefixes; they are not necessarily the display ticker on the decision date. Contributions explain accounting, not causality.</p><label>Find security <input id="search" placeholder="NVDA, PLTR, …"></label><div class="scroll"><table id="stocks"></table></div>
<p><a href="annual.csv">Annual CSV</a> · <a href="monthly-selections.csv">Monthly selections CSV</a> · <a href="stock-contributions.csv">All contributions CSV</a> · <a href="comparison.json">Evidence JSON</a> · <a href="manifest.json">Artifact hashes</a></p><h2>Evidence and limits</h2><ul id="checks"></ul><ul id="limits"></ul>
<script>const D=DATA;const $=id=>document.getElementById(id);const pct=x=>x==null?'—':(100*x).toFixed(2)+'%';const num=x=>x==null?'—':x.toFixed(2);const usd=x=>'$'+x.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});const table=(id,heads,rows)=>{$(id).replaceChildren();let tr=document.createElement('tr');heads.forEach(h=>{let c=document.createElement('th');c.textContent=h;tr.append(c)});$(id).append(tr);rows.forEach(row=>{let tr=document.createElement('tr');row.forEach(v=>{let td=document.createElement('td');td.textContent=v;tr.append(td)});$(id).append(tr)})};const names=Object.fromEntries(D.runs.map(r=>[r.case,r.name]));
table('full',['Case','CAGR','Max DD','Sharpe','Calmar','Longest UW sessions / days','Average gross','Peak sector*','End equity'],D.runs.map(r=>[r.name,pct(r.cagr),pct(-r.dd),num(r.sharpe),num(r.calmar),r.longest_uw+' / '+r.longest_uw_days,pct(r.average_gross),r.case==='spy'?'Not look-through':pct(r.peak_sector_gross),usd(r.end)]));
for(let y=2020;y<=2025;y++)$('year').add(new Option(y,y));for(const r of D.runs)$('case').add(new Option(r.name,r.case));for(const m of [...new Set(D.monthly_selections.map(r=>r.date))])$('month').add(new Option(m,m));
function renderAnnual(){table('annual',['Case','Return','Annual-reset DD','Sharpe','Calmar','Longest UW sessions','Underwater sessions'],D.annual.filter(r=>r.year===$('year').value).map(r=>[names[r.case],pct(r.ret),pct(-r.dd),num(r.sharpe),num(r.annual_calmar),r.longest_uw,r.uw]))}
function renderDetail(){const c=$('case').value;table('monthly',['Rank','Security ID','Sector','Gate snapshot','Eligible count','Base target','Sector target','Effective target'],D.monthly_selections.filter(r=>r.case===c&&r.date===$('month').value).map(r=>[r.rank,r.security_id,r.sector,r.gate,r.case==='spy'?'N/A':r.ready,pct(r.base_target),pct(r.sector_target),pct(r.effective_target)]));const q=$('search').value.toLowerCase();table('stocks',['Security ID','Last observed sector','Net P&L contribution','Fees (included)'],D.contributions.filter(r=>r.case===c&&r.security_id.toLowerCase().includes(q)).sort((a,b)=>b.pnl_usd-a.pnl_usd).map(r=>[r.security_id,r.sector,usd(r.pnl_usd),usd(r.fees_usd)]))}
$('year').onchange=renderAnnual;$('case').onchange=renderDetail;$('month').onchange=renderDetail;$('search').oninput=renderDetail;renderAnnual();renderDetail();for(const key of ['checks','limits'])for(const text of D[key]){let li=document.createElement('li');li.textContent=text;$(key).append(li)};</script></html>'''.replace('DATA',data)
    (OUT/'index.html').write_text(html)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    evidence=dict(study='stock-risk-v1',status=result['status'],attempts=result['attempts'],checks=result['checks'],limits=result['limits'],sources=json.loads((ROOT/'research/plans/stock-risk-v1.json').read_text())['source_hashes'],artifacts=manifest)
    (ROOT/'docs/tasks/evidence/2026-10-26-stock-risk-ablation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print([(r['case'],round(100*r['cagr'],2),round(-100*r['dd'],2),r['longest_uw']) for r in result['runs']])
    print('Annual rows',len(result['annual']),'selection rows',len(result['monthly_selections']),'contributions',len(result['contributions']))


if __name__=='__main__':build()
