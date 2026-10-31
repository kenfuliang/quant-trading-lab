"""Validate saved QC summary outputs and render; never launches financial runs."""
from pathlib import Path
import csv
from datetime import date
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'.local/sector-momentum-v1'
OUT = ROOT/'.local/performance/sector-momentum-v1'
MODES = ['hold','equal','momentum','gate']
NAMES = dict(hold='SPY buy and hold',equal='Equal-weight sectors',momentum='Sector momentum',gate='Original SPY risk gate')


def validate(records):
    annual = []
    overall = []
    for mode in MODES:
        rows = records[mode]
        if len(rows) != 10 or {r['year'] for r in rows} != {str(y) for y in range(2017,2026)}|{'ALL'}:
            raise ValueError('Missing/duplicate summary year: '+mode)
        if any(r['mode']!=mode or r['study']!='sector-v1' for r in rows):
            raise ValueError('Wrong study/case')
        years = sorted([r for r in rows if r['year']!='ALL'],key=lambda r:r['year'])
        full = next(r for r in rows if r['year']=='ALL')
        if full['rejects'] or full['min_cash']<-.01 or full['max_gross']>1.000001:
            raise ValueError('Execution guard failed: '+mode)
        if full['first']!='2017-01-03' or full['last']!='2025-12-31':
            raise ValueError('Incomplete date range')
        product = 1.
        nav = 300000.
        for r in years:
            product *= 1+r['ret']
            nav *= 1+r['ret']
            if abs(nav-r['end'])>.01:
                raise ValueError('Annual NAV compounding mismatch')
            if r['annual_calmar'] is not None and not math.isclose(r['annual_calmar'],r['ret']/abs(r['dd']),abs_tol=1e-10):
                raise ValueError('Annual Calmar mismatch')
            if not 0 <= r['uw'] <= r['n'] or not 0 <= r['global_uw'] <= r['n']:
                raise ValueError('Invalid underwater counts')
        if abs(product-1-full['ret'])>1e-10 or abs(nav-full['end'])>.01:
            raise ValueError('Full NAV compounding mismatch')
        if sum(r['n'] for r in years)!=full['n'] or sum(r['global_uw'] for r in years)!=full['uw']:
            raise ValueError('Session/underwater totals mismatch')
        n=full['n'];s=sum(r['return_sum'] for r in years);ss=sum(r['return_square_sum'] for r in years)
        sd=math.sqrt(max(0,(ss-s*s/n)/(n-1)))
        sharpe=s/n/sd*math.sqrt(252) if sd>1e-15 else None
        if (sharpe is None)!=(full['sharpe'] is None) or (sharpe is not None and not math.isclose(sharpe,full['sharpe'],abs_tol=1e-10)):
            raise ValueError('Sharpe aggregation mismatch')
        expected_cagr=(full['end']/300000.)**(365.25/(date(2025,12,31)-date(2016,12,30)).days)-1
        if not math.isclose(full['cagr'],expected_cagr,abs_tol=1e-10):
            raise ValueError('CAGR calendar-time mismatch')
        expected_calmar=full['cagr']/abs(full['dd']) if full['dd']<0 else None
        if (full['calmar'] is None)!=(expected_calmar is None) or (expected_calmar is not None and not math.isclose(full['calmar'],expected_calmar,abs_tol=1e-10)):
            raise ValueError('Full Calmar mismatch')
        if full['dd']>min(r['dd'] for r in years)+1e-10:
            raise ValueError('Full drawdown shall include annual peaks')
        if not math.isclose(full['uw_fraction'],full['uw']/n,abs_tol=1e-12):
            raise ValueError('Underwater fraction mismatch')
        annual.extend(years);overall.append(full)
    signatures={(r['n'],r['calendar_hash'],r['first'],r['last']) for r in overall}
    if len(signatures)!=1:
        raise ValueError('Cases have different session calendars')
    for year in range(2017,2026):
        if len({r['n'] for r in annual if r['year']==str(year)})!=1:
            raise ValueError('Annual session counts differ')
    return annual, overall


def build():
    ledger=json.loads((RAW/'attempts.json').read_text())
    if len(ledger['attempts'])>ledger['max_financial_attempts']:
        raise ValueError('Budget exceeded')
    records={m:[json.loads(x) for x in json.loads((RAW/f'final-{m}-summary-cells.json').read_text())] for m in MODES}
    annual,overall=validate(records)
    final_attempts=[a for a in ledger['attempts'] if a.get('selected_for_final_comparison')]
    if len(final_attempts)!=4 or {a['mode'] for a in final_attempts}!=set(MODES):
        raise ValueError('Four completed selected cases required')
    source=(ROOT/'research/quantconnect/sector_comparison.py').read_text()
    for a in final_attempts:
        saved=RAW/f"{a['attempt']:02d}-{a['mode']}-source.py"
        expected=source.replace('MODE = "hold"',f'MODE = "{a["mode"]}"')
        if saved.read_text()!=expected or hashlib.sha256(saved.read_bytes()).hexdigest()!=a['source_sha256']:
            raise ValueError('Case source differs beyond MODE')
        if a['status']!='completed-summary-captured':
            raise ValueError('Case not confirmed complete')
    paths=[RAW/f'final-{m}-summary-cells.json' for m in MODES]
    receipt={'study_id':'sector-momentum-v1','status':'completed-summary-audited-development-diagnostic',
             'git_sha':ledger['git_sha'],'completed_utc':ledger['completed_utc'],
             'cloud_engine_observed':'LEAN 2.5.0.0.18205; Foundation Default; exact cloud dependency inventory unexported',
             'attempts':ledger['attempts'],'protocol_amendment':ledger['amendment'],
             'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths+[ROOT/'research/quantconnect/sector_comparison.py',ROOT/'research/plans/sector-momentum-v1-execution-repair.json',ROOT/'research/quantconnect/sector_metrics.py',ROOT/'requirements.lock.txt']},
             'checks':['4 cases, 9 annual years each','matching session-calendar hashes and annual counts','annual/end NAV compounding within USD0.01','Sharpe aggregated from annual return moments','Calmar formulas','carried-high-water underwater count summation','zero rejects, positive closing cash and gross<=1','selected sources differ only by MODE','8 attempt cap respected'],
             'limitations':['In-cloud daily NAV metrics; no raw data or daily NAV exported','No independent daily ledger, fills, corporate action or slippage audit','Calendar matched across cases, not independently qualified against exchange calendar','Historical development sample, not alpha or untouched holdout','Daily-close no-borrow checks do not measure intraday financing','Ten-sector static ETF universe excludes XLC and 2008; sector definitions change','Native vendor Sharpe differs from our explicit zero-RF daily metric']}
    OUT.mkdir(parents=True,exist_ok=True)
    data={'names':NAMES,'annual':annual,'overall':overall,'evidence':receipt}
    (OUT/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
    fields=['mode','year','n','ret','dd','sharpe','annual_calmar','uw_fraction','global_uw_fraction','longest_uw','longest_uw_days','censored','end']
    with (OUT/'annual.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(annual)
    (OUT/'index.html').write_text(PAGE.replace('PAYLOAD',json.dumps(data).replace('</','<\\/')))
    outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps({'study_id':'sector-momentum-v1','outputs_sha256':outputs},indent=2)+'\n')
    (ROOT/'docs/tasks/evidence/2026-10-25-sector-momentum-comparison.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'financial_attempts':len(ledger['attempts']),'annual_rows':len(annual),'overall':overall},indent=2))

PAGE='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sector momentum · matched comparison</title><style>
body{margin:0;background:#f3f5f7;color:#182b3a;font:15px system-ui}main{max-width:1320px;margin:auto;padding:28px}h1{font-size:34px;margin:8px 0}h2{margin-top:28px}p{line-height:1.6;max-width:105ch}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#587080}.notice{border-left:4px solid #a87314;background:#fff3d9;padding:12px 18px}.cards{display:grid;grid-template-columns:repeat(4,minmax(200px,1fr));gap:12px}.card{background:white;border:1px solid #d7e0e6;border-top:5px solid var(--color);padding:18px;border-radius:8px}.card h2{font-size:18px;margin:0 0 12px}.big{font-size:28px;font-weight:700}.small{font-size:12px;color:#526677}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;background:white}th,td{text-align:right;padding:9px;border-bottom:1px solid #dde4e9;white-space:nowrap}th{background:#e4ecf2}td:first-child,th:first-child{text-align:left}.scroll{overflow:auto}.best{background:#e2f2e9;font-weight:700}select{font:inherit;padding:8px;margin:8px}svg{background:white;width:100%;height:auto}.legend{display:flex;gap:18px;flex-wrap:wrap}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}a{color:#0a5791}details{background:white;padding:14px;margin:18px 0}@media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}}@media(max-width:500px){.cards{grid-template-columns:1fr}main{padding:15px}}
</style><main><div class="eyebrow">Quant trading lab · 26 October 2026 · bounded development study</div><h1>Does sector selection improve the tradeoff?</h1><p>2017–2025 · $300,000 per account · ten sector ETFs · 98% target budget · prior-close-sized next-open orders · $1/order + configured 5bp slippage. No strategy tuning.</p><div class="notice"><b>Matched repaired execution:</b> all four selected runs use the same simulated buying-power settings and passed closing cash/exposure checks. Eight attempts include a duplicate control, two superseded controls and one stopped momentum path. This is historical development evidence; 2008 is outside the window.</div><div class="cards" id="cards"></div><h2>Year by year</h2><p>Choose one measure to compare all four accounts. Annual drawdown and longest underwater run reset at the year boundary. <b>Carried-peak underwater %</b> instead retains every earlier high, exposing losses that remain unrecovered across years.</p><label>Measure <select id="metric"><option value="ret">Annual return</option><option value="dd">Annual maximum drawdown</option><option value="sharpe">Annual Sharpe</option><option value="annual_calmar">Annual Calmar</option><option value="global_uw_fraction">Carried-peak underwater %</option><option value="longest_uw">Year-reset longest underwater run (sessions)</option></select></label><div class="legend" id="legend"></div><div id="chart"></div><div class="scroll"><table id="matrix"></table></div><h2>All annual measurements</h2><div class="scroll"><table id="detail"></table></div><details><summary>Definitions, controls and limits</summary><p>Sector momentum selects three of XLB, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY by trailing 252-session total return and rebalances monthly. Equal weight rebalances all ten monthly. SPY buy and hold makes one entry; dividends stay in cash. The original gate resizes SPY daily using its unchanged 2004-seeded state. These dividend/rebalance policies are intentional differences.</p><p>Sharpe uses daily closing-NAV simple returns, sample standard deviation, sqrt252 and zero risk-free rate. Full Calmar = calendar-time CAGR / |full maximum drawdown|. Annual Calmar = annual return / |within-year drawdown|. Undefined ratios appear as —. Underwater means below the account's prior high, not necessarily below initial capital. Calendar days run from peak through last underwater close, excluding recovery day. An unrecovered final episode is censored.</p><p>Margin plumbing permits pending-sale credit; the target remains unlevered. Positive closing cash does not independently verify intraday borrowing, fills or financing. All metrics were computed inside QC; only aggregate summaries were captured. Matching session hashes and algebra checks do not replace an independent daily ledger or exchange calendar audit. Later sector classification changes and today's fixed ETF set are research limitations.</p></details><p><a href="annual.csv">Annual CSV</a> · <a href="comparison.json">Metrics and provenance</a> · <a href="manifest.json">Artifact hashes</a> · <a href="https://www.quantconnect.com/project/38460130">Hosted project</a></p></main><script>
const data=PAYLOAD,modes=['hold','equal','momentum','gate'],colors=['#235fa0','#8b69a9','#c07724','#25816b'];
const pct=x=>x==null?'—':(x*100).toFixed(2)+'%',num=x=>x==null?'—':x.toFixed(2);const fmt=(k,v)=>['ret','dd','global_uw_fraction','uw_fraction'].includes(k)?pct(v):(k==='longest_uw'?String(v):num(v));
const years=Array.from({length:9},(_,i)=>String(2017+i));const get=(m,y)=>data.annual.find(r=>r.mode===m&&r.year===y);
document.getElementById('cards').innerHTML=data.overall.map((r,i)=>`<article class="card" style="--color:${colors[i]}"><h2>${data.names[r.mode]}</h2><div class="big">${pct(r.cagr)}</div><div class="small">CAGR after modeled costs</div><p>${pct(r.dd)} max drawdown<br>${num(r.sharpe)} Sharpe · ${num(r.calmar)} Calmar<br>${pct(r.uw_fraction)} closes underwater<br><b>${r.longest_uw} sessions</b> longest underwater<br>${r.longest_uw_days} calendar days<br>$${Math.round(r.end).toLocaleString()} ending NAV</p><div class="small">$${r.fees.toLocaleString()} fees · ${r.rejects} rejects<br>Unrecovered at end: ${r.censored?'yes':'no'}</div></article>`).join('');
document.getElementById('legend').innerHTML=modes.map((m,i)=>`<span><i class="dot" style="background:${colors[i]}"></i>${data.names[m]}</span>`).join('');
function render(){let k=document.getElementById('metric').value;let vals=data.annual.map(r=>r[k]).filter(v=>v!=null),lo=Math.min(0,...vals),hi=Math.max(0,...vals);if(hi===lo)hi=lo+1;let pad=(hi-lo)*.1;hi+=pad;lo-=pad;const sy=v=>25+(hi-v)/(hi-lo)*240,base=sy(0);let s='<svg viewBox="0 0 1100 325" role="img" aria-label="Year-by-year strategy comparison">';for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,y=sy(v);s+=`<line x1="62" x2="1090" y1="${y}" y2="${y}" stroke="#d8e1e9"/><text x="4" y="${y+4}" font-size="12">${fmt(k,v)}</text>`}years.forEach((y,i)=>{let x=78+i*113;modes.forEach((m,j)=>{let v=get(m,y)[k];if(v!=null)s+=`<rect x="${x+j*22}" y="${Math.min(base,sy(v))}" width="18" height="${Math.max(1,Math.abs(sy(v)-base))}" fill="${colors[j]}"><title>${y} ${data.names[m]}: ${fmt(k,v)}</title></rect>`});s+=`<text x="${x+25}" y="298" font-size="13">${y}</text>`});document.getElementById('chart').innerHTML=s+'</svg>';let lower=['global_uw_fraction','longest_uw'].includes(k);document.getElementById('matrix').innerHTML='<thead><tr><th>Year</th>'+modes.map(m=>`<th>${data.names[m]}</th>`).join('')+'</tr></thead><tbody>'+years.map(y=>{const vs=modes.map(m=>get(m,y)[k]).filter(v=>v!=null),best=lower?Math.min(...vs):Math.max(...vs);return '<tr><td>'+y+'</td>'+modes.map(m=>{let v=get(m,y)[k];return `<td class="${v!=null&&v===best?'best':''}">${fmt(k,v)}</td>`}).join('')+'</tr>'}).join('')+'</tbody>'}
document.getElementById('metric').onchange=render;render();
document.getElementById('detail').innerHTML='<thead><tr><th>Year / portfolio</th><th>Return</th><th>Max DD</th><th>Sharpe</th><th>Calmar</th><th>Year-reset UW</th><th>Carried-peak UW</th><th>Longest UW sessions</th><th>UW calendar days</th></tr></thead><tbody>'+years.map(y=>modes.map(m=>{let r=get(m,y);return `<tr><td>${y} · ${data.names[m]}</td><td>${pct(r.ret)}</td><td>${pct(r.dd)}</td><td>${num(r.sharpe)}</td><td>${num(r.annual_calmar)}</td><td>${pct(r.uw_fraction)}</td><td>${pct(r.global_uw_fraction)}</td><td>${r.longest_uw}</td><td>${r.longest_uw_days}</td></tr>`}).join('')).join('')+'</tbody>';
</script></html>'''

if __name__=='__main__':build()
