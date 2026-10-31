"""Build a local browser comparison from preserved QuantConnect UI evidence."""
import csv
import hashlib
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'.local/quantconnect-comparison-v1'
OUT = ROOT/'.local/performance/quantconnect-spy-v1'
NAMES = {'hold':'Buy and hold','ema':'EMA50/200','gate':'Original risk gate'}
IDS = {'hold':'82cd58e69dced78daeface1fade8c47e','ema':'3efdaac032eea7d234f8a3e21eba47c8','gate':'6421cb33f5a1113c23b79cad36d39fe5'}

def build():
    overall, annual, artifacts = [], [], {}
    fields={'cagr_pct':'Compounding Annual Return','max_drawdown_pct':'Drawdown','sharpe_native':'Sharpe Ratio','end_equity_usd':'End Equity','orders_native':'Total Orders','fees_usd':'Total Fees','drawdown_recovery_native':'Drawdown Recovery'}
    for mode in NAMES:
        paths=[SOURCE/f'{mode}-overview.txt', SOURCE/f'{mode}-log-cells.json']
        for p in paths:
            artifacts[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        lines=[x.strip() for x in paths[0].read_text().split('Download Results',1)[1].splitlines() if x.strip()]
        row={'mode':mode,'name':NAMES[mode],'backtest_id':IDS[mode]}
        for key,label in fields.items():
            row[key]=float(lines[lines.index(label)+1].replace('%','').replace('$','').replace(',',''))
        logs=json.loads(paths[1].read_text())
        records=[json.loads(t) for t in logs if t.startswith('{') and 'annual_return' in t]
        summaries=[json.loads(t) for t in logs if t.startswith('{') and 'sessions' in t]
        assert len(summaries)==1
        summary=summaries[0]
        assert summary['mode']==mode and summary['sessions']==5283
        assert [r['year'] for r in records]==[str(y) for y in range(2005,2026)]
        assert all(r['mode']==mode and math.isfinite(r['annual_return']) and -1<=r['within_year_max_drawdown']<=0 for r in records)
        product=300000*math.prod(1+r['annual_return'] for r in records)
        assert abs(product-row['end_equity_usd'])<.01, (mode,product)
        row.update(summary)
        row['annual_compounding_residual_usd']=product-row['end_equity_usd']
        row['calmar_approx_from_native_rounded']=row['cagr_pct']/row['max_drawdown_pct']
        row['comparison_status']='conditional: 3 buying-power rejections' if summary['rejected_orders'] else 'completed: no rejected orders'
        overall.append(row)
        annual.extend(records)
    OUT.mkdir(parents=True,exist_ok=True)
    data={'overall':overall,'annual':annual,'artifact_sha256':artifacts,'method':'Preserved rendered overview text and DOM table log cells; no hidden application state or API calls','annual_drawdown_definition':'Reset peak to previous year end; compute worst closing NAV drop within calendar year, including opening baseline','limitations':['Development history, no untouched test or alpha claim.','EMA had3buying-power rejections; results reflect those actual simulation outcomes and do not qualify ideal order-policy parity.','Buy-and-hold and EMA accumulate dividends in cash during held spells; gate daily resizing can reinvest.','Native Sharpe and recovery definitions remain vendor-defined; not equated to local metric implementation.','Annual equity compounding is checked against displayed ending NAV; independent daily accounting/fill audit not performed.','Constant5bps model configured; realized per-fill slippage not independently verified.']}
    (OUT/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
    with (OUT/'annual.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['mode','year','annual_return','within_year_max_drawdown']);w.writeheader();w.writerows(annual)
    payload=json.dumps(data).replace('</','<\\/')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SPY comparison · QuantConnect</title><style>
body{font:16px system-ui;margin:0;background:#f5f7fa;color:#182635}main{max-width:1200px;margin:auto;padding:32px}h1{margin-bottom:6px}p{max-width:100ch;line-height:1.55}.notice{background:#fff0d7;border-left:5px solid #ac6500;padding:15px}.cards{display:flex;gap:14px;flex-wrap:wrap}.card{flex:1;min-width:240px;background:white;border:1px solid #ccd5df;border-top:5px solid var(--c);padding:18px;border-radius:8px}.number{font-size:26px;font-weight:700}table{border-collapse:collapse;background:white;width:100%;font-variant-numeric:tabular-nums}th,td{padding:11px 12px;border-bottom:1px solid #dbe2e9;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#e7edf4}select{font:inherit;padding:8px}svg{width:100%;height:auto;background:white}.small{font-size:13px;color:#526172}.scroll{overflow:auto}a{color:#12549d}.best{font-weight:750;background:#e7f2ee}.negative{color:#a32132}footer{margin:24px 0}.badge{font-size:13px;font-weight:600}button{font:inherit;padding:7px 12px;cursor:pointer}
</style><main><p class="small">Quant trading lab · 25 October 2026 · hosted development diagnostic</p><h1>SPY: return versus protection</h1><p>2005–2025 · $300,000 starting cash · long/cash · prior-close-sized next-open orders · $1/order plus a configured 5bps slippage model. Free QuantConnect Community B-MICRO.</p><p class="notice"><b>EMA is conditional:</b> three simulated orders were rejected for buying power. No rejected orders in the other two completed runs. The failed initial zero-trade run is excluded and preserved. These are model outcomes, not forecasts.</p><div class="cards" id="cards"></div><h2>Year-by-year comparison</h2><p>Annual drawdown resets its peak at the previous year-end. It differs from full-period drawdown, which carries peaks across years. Gate 0% in 2009–2010 reflects staying in cash and missing the rebound.</p><label>Chart <select id="metric"><option value="annual_return">Annual return</option><option value="within_year_max_drawdown">Within-year maximum drawdown</option></select></label><div id="chart"></div><div class="scroll"><table id="annual"></table></div><h2>Interpretation and limits</h2><ul><li>Buy and hold earned the most; the original gate reduced drawdown but sacrificed growth.</li><li>QC reports recovery values of 1,800 for hold, 805 for EMA and 2,109 for gate. Units/conventions are vendor-defined; a smaller drawdown did not imply a faster recovery.</li><li>Buy and hold leaves dividends in cash; the gate resizes daily. This is not a perfectly isolated gate ablation or a fully reinvested SPY benchmark.</li><li>All three logged 5,283 sessions and 84 dividend events. No SPY split events occurred; this does not test general stock split/delisting handling.</li><li>Annual returns compound to displayed ending NAV within one cent. Native daily ledgers, fills, Sharpe and slippage have not been independently reconciled.</li></ul><p><a href="annual.csv">Annual CSV</a> · <a href="comparison.json">Evidence and definitions</a> · <a href="https://www.quantconnect.com/project/38460130">QuantConnect project</a></p><footer class="small">The three rules were frozen before viewing outcomes. Source snapshots, technical failures and attempted runs are preserved locally. No paid upgrade, broker connection or deployment.</footer></main><script>const data=PAYLOAD;
const modes=['hold','ema','gate'], colors=['#225aa0','#bd6a10','#278675']; const names={hold:'Buy and hold',ema:'EMA50/200',gate:'Original gate'};const pct=x=>(100*x).toFixed(2)+'%';
document.getElementById('cards').innerHTML=data.overall.map((r,i)=>`<article class="card" style="--c:${colors[i]}"><h2>${r.name}</h2><div class="number">${r.cagr_pct.toFixed(2)}% CAGR</div><p>${r.max_drawdown_pct.toFixed(1)}% max drawdown<br>$${r.end_equity_usd.toLocaleString('en-US',{maximumFractionDigits:0})} ending equity<br>${r.orders_native} orders · $${r.fees_usd.toFixed(0)} fees<br>Native Sharpe ${r.sharpe_native.toFixed(3)}<br>Approx. Calmar ${r.calmar_approx_from_native_rounded.toFixed(3)}</p><span class="badge">${r.comparison_status}</span></article>`).join('');
const years=Array.from({length:21},(_,i)=>String(2005+i)); const get=(m,y)=>data.annual.find(r=>r.mode===m&&r.year===y);
document.getElementById('annual').innerHTML='<thead><tr><th>Year</th>'+modes.map(m=>`<th colspan="2">${names[m]}</th>`).join('')+'</tr><tr><th></th>'+modes.map(()=>'<th>Return</th><th>Max DD</th>').join('')+'</tr></thead><tbody>'+years.map(y=>{const best=Math.max(...modes.map(m=>get(m,y).annual_return));return '<tr><td>'+y+'</td>'+modes.map(m=>{const r=get(m,y);return `<td class="${r.annual_return===best?'best ':''}${r.annual_return<0?'negative':''}">${pct(r.annual_return)}</td><td>${pct(r.within_year_max_drawdown)}</td>`}).join('')+'</tr>'}).join('')+'</tbody>';
function draw(){const k=document.getElementById('metric').value;const lo=-.5,hi=.4,base=55+(hi/(hi-lo))*260,sy=v=>55+((hi-v)/(hi-lo))*260;let s='<svg viewBox="0 0 1160 370" role="img" aria-label="Annual strategy comparisons">';for(let t=-.5;t<=.401;t+=.1){const yy=sy(t);s+=`<line x1="52" x2="1145" y1="${yy}" y2="${yy}" stroke="#dbe2e9"/><text x="8" y="${yy+4}" font-size="12">${(t*100).toFixed(0)}%</text>`}years.forEach((y,i)=>{const x=60+i*51.4;modes.forEach((m,j)=>{const v=get(m,y)[k],yy=sy(v);s+=`<rect x="${x+j*13}" y="${Math.min(base,yy)}" width="11" height="${Math.max(1,Math.abs(base-yy))}" fill="${colors[j]}"><title>${y} ${names[m]} ${pct(v)}</title></rect>`});s+=`<text x="${x+8}" y="340" transform="rotate(-45 ${x+8} 340)" font-size="11">${y}</text>`});s+='</svg>';document.getElementById('chart').innerHTML=s}document.getElementById('metric').onchange=draw;draw();</script></html>'''.replace('PAYLOAD',payload)
    (OUT/'index.html').write_text(page)
    print(json.dumps({'path':str(OUT),'annual_rows':len(annual),'all_annual_compounding_residuals_below_one_cent':True,'overall':overall},indent=2))

if __name__=='__main__':
    build()
