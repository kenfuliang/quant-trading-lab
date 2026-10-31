"""Render saved funded-policy diagnostics against preserved ablation controls."""
from pathlib import Path
import csv,hashlib,json,math
from build_qc504_ablation import PAGE as BASE_PAGE, NAMES
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/qc504-funded-v1';OUT=ROOT/'.local/performance/qc504-funded-v1'
CASES=('ensemble','t10','t11','s2','s3')
def validate(rows,case):
    if not rows or any(r.get('study')!='qc504-funded-v1' or r.get('case')!=case for r in rows):raise ValueError('Wrong study/case')
    full=[r for r in rows if r.get('kind')=='overall'];annual=sorted([r for r in rows if r.get('kind')=='annual'],key=lambda r:r['year'])
    if len(full)!=1 or [r['year'] for r in annual]!=[str(y) for y in range(2020,2026)]:raise ValueError('Incomplete summaries')
    f=full[0];nav=10000.;mom=squares=0.;n=uw=0
    for r in annual:
        nav*=1+r['ret'];mom+=r['return_sum'];squares+=r['return_square_sum'];n+=r['n'];uw+=r['global_uw']
        if not math.isclose(nav,r['end'],abs_tol=.1,rel_tol=1e-8):raise ValueError('Annual NAV mismatch')
        if r['annual_calmar'] is not None and not math.isclose(r['ret']/abs(r['dd']),r['annual_calmar'],abs_tol=1e-6):raise ValueError('Annual Calmar mismatch')
    if not math.isclose(nav,f['end'],abs_tol=.1,rel_tol=1e-8) or n!=f['n'] or uw!=f['uw']:raise ValueError('Totals mismatch')
    sd=math.sqrt(max(0,(squares-mom*mom/n)/(n-1)))
    if sd>1e-15 and not math.isclose(mom/n/sd*math.sqrt(252),f['sharpe'],abs_tol=1e-5):raise ValueError('Sharpe mismatch')
    if f['calmar'] is not None and not math.isclose(f['cagr']/abs(f['dd']),f['calmar'],abs_tol=1e-8):raise ValueError('Calmar mismatch')
    a=next(r for r in rows if r['kind']=='assets')
    f['pnl_residual_usd']=a['residual_usd']
    f['status']='conditional: rejected orders' if f['rejects'] else 'complete: no rejected orders'
    return f,annual


def build():
    ledger=json.loads((RAW/'attempts.json').read_text());plan=json.loads((ROOT/'research/plans/qc504-funded-v1.json').read_text())
    basepath=ROOT/'.local/performance/qc504-ablation-v1/comparison.json';baseline=json.loads(basepath.read_text())
    runs=[];annual=[];missing=[]
    for case in CASES:
        path=RAW/f'{case}-summary-cells.json'
        if not path.exists():missing.append(case);continue
        rows=[json.loads(x) for x in json.loads(path.read_text())];f,ys=validate(rows,case)
        if not math.isclose(sum(y['financing_usd'] for y in ys),f['financing_usd'],abs_tol=1e-8):raise ValueError('Annual funding total mismatch')
        if f['funding_debit_error']>1e-4:raise ValueError('Funding NAV debit failed')
        f['status']='failed-zero-rejection-acceptance' if f['rejects'] else 'passed observed zero-rejection/debit checks'
        runs.append(f);annual+=ys
    if len({r['calendar_hash'] for r in runs+baseline['runs']})!=1:raise ValueError('Old/new calendar mismatch')
    files=['scripts/prepare_qc504_funded.py','scripts/qc504_funded_budget.py','scripts/parse_qc504_funded_fragments.py','scripts/build_qc504_funded.py','scripts/build_qc504_ablation.py','research/quantconnect/qc504_funded_policy.py','research/quantconnect/sector_metrics.py','research/plans/qc504-funded-v1.json','tests/test_qc504_funded.py']
    receipt=dict(study_id=plan['study_id'],status='complete' if not missing else 'partial',missing=missing,failed_acceptance=[r['case'] for r in runs if r['rejects'] or r['fills']==0],attempts=ledger['attempts'],attempts_used=len(ledger['attempts']),closed_utc=ledger.get('closed_utc'),unused_repair_slots=ledger.get('unused_repair_slots'),git_sha=ledger['git_sha'],engine='LEAN2.5.0.0.18209 observed',checks=['Annual/full NAV and return moments','Annual/full Calmar','Matching old/new session hash','Global underwater totals','Annual/total financing','Every funding debit matched same-step NAV reduction'],baseline_sha256=hashlib.sha256(basepath.read_bytes()).hexdigest(),source_hashes=plan['source_hashes'],code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(RAW.glob('*summary-cells.json'))+list(RAW.glob('*terminal-fragments.json'))},limits=['Combined staging/90pct sizing/funding intervention; not isolated financing effect','Extra rotation delay and clipping alter exposure','6pct flat ACT/360 assumption, not broker historical schedule','Daily close debt/marks omit intraday funding and risk','Previously exposed development sample; no new alpha evidence','Vendor price snapshot not independently hashed; matching calendar hashes verify session coverage only','Embedded ETF leverage/expenses reflected in prices; underlying capacity unqualified','Native accounting plus explicit financing checks, not independent fill/cash ledger'])
    data=dict(names=NAMES,runs=runs,annual=annual,baseline=baseline,evidence=receipt)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
    with (OUT/'annual.csv').open('w') as fp:
        w=csv.DictWriter(fp,fieldnames=['case','year','ret','dd','sharpe','annual_calmar','global_uw','n','longest_uw','financing_usd','end'],extrasaction='ignore');w.writeheader();w.writerows(annual)
    (OUT/'index.html').write_text(page().replace('PAYLOAD',json.dumps(data).replace('</','<\\/')))
    (ROOT/'docs/tasks/evidence/2026-10-26-qc504-funded-execution.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n')
    print(json.dumps(dict(runs=runs,annual_rows=len(annual),missing=missing,failed=receipt['failed_acceptance']),indent=2))

def page():
    s=BASE_PAGE.replace('504 · sleeve ablation','504 · funded execution').replace('Frozen full-budget ablation · Five cases, maximum seven attempts (reporting amendment)','Frozen staged execution and financing · Five cases, maximum seven attempts').replace('Do four sleeves improve the tradeoff?','What changes after execution and funding controls?')
    s=s.replace('original IB margin/fee defaults · unchanged signal and MOO order policy. Standalone sleeves receive the full budget; ensemble retains four quarter budgets.','original IB margin/fees · unchanged signals ·90% target budget · reductions fill before buys ·6% debit ACT/360; credit interest zero.')
    s=s.replace('Financing, embedded leverage, independent accounting and capacity remain unqualified.','Financing uses an illustrative fixed6% rate. Underlying leverage, independent accounting and capacity remain unqualified.')
    s=s.replace('Frozen copied source → ensemble + four standalone sleeves → matched metrics → tradeoffs, not promotion','Close signal → staged reductions then buys → cash/margin checks → financing debit → matched diagnostics')
    s=s.replace('Five complete summaries · all four standalone sleeves have rejected orders and are conditional; ensemble has zero. Sorting is descriptive.','Five complete summaries · zero observed rejected orders in every case; financing checks passed. Sorting is descriptive.')
    s=s.replace('<h2>Overall comparison</h2>','<h2>New-policy overall comparison</h2>')
    s=s.replace('<h2>Time underwater</h2>','<h2>Prior versus new policy</h2><p>Same dates, starting capital, slippage and fee model; staging, allocation and funding change together. This does not isolate the cost of financing.</p><div class="scroll"><table id="beforeafter"></table></div><h2>Financing and execution stages</h2><div class="scroll"><table id="funding"></table></div><h2>Time underwater</h2>')
    s=s.replace('<label>Metric <select id="metric">','<label>Policy <select id="policy"><option value="new">New staged/funded</option><option value="old">Prior ablation</option></select></label> <label>Metric <select id="metric">')
    s=s.replace('<option value="global_uw">Carried-peak underwater fraction</option>','<option value="global_uw">Carried-peak underwater fraction</option><option value="financing_usd">Financing USD (new policy)</option>')
    s=s.replace("function years(){let k=", "function years(){let activeAnnual=document.getElementById('policy').value==='old'?d.baseline.annual:d.annual;let k=")
    s=s.replace('let r=d.annual.find(', 'let r=activeAnnual.find(')
    s=s.replace("document.getElementById('metric').onchange=years;", "document.getElementById('metric').onchange=years;document.getElementById('policy').onchange=years;")
    s=s.replace('Standalone allocation uses full capital, not a 25% sleeve plus 75% cash. This is not realized inside-ensemble attribution.','Each case uses the same90% target scaling before cash/margin constraints. Rotation delays and clipping are reported; risk/exposure are not equalized.')
    s=s.replace('Native-book P&L residual is not an independent reconstruction of cash/fills/dividends.','Native P&L plus explicit financing residual is not an independent reconstruction of fills, cash or dividends. Zero funding on a no-debt path does not test rate sensitivity.')
    add="""document.getElementById('beforeafter').innerHTML='<tr><th>Case</th><th>Prior CAGR</th><th>New CAGR</th><th>Prior DD</th><th>New DD</th><th>Prior Sharpe</th><th>New Sharpe</th><th>Prior Calmar</th><th>New Calmar</th><th>Prior longest UW</th><th>New longest UW</th><th>Prior rejects</th><th>New rejects</th></tr>'+d.runs.map(r=>{let b=d.baseline.runs.find(x=>x.case===r.case);return `<tr><td>${d.names[r.case]}</td><td>${pct(b.cagr)}</td><td>${pct(r.cagr)}</td><td>${pct(b.dd)}</td><td>${pct(r.dd)}</td><td>${num(b.sharpe)}</td><td>${num(r.sharpe)}</td><td>${num(b.calmar)}</td><td>${num(r.calmar)}</td><td>${b.longest_uw}</td><td>${r.longest_uw}</td><td>${b.rejects}</td><td>${r.rejects}</td></tr>`}).join('');document.getElementById('funding').innerHTML='<tr><th>Case</th><th>Interest USD</th><th>Debt calendar days</th><th>Sell batches</th><th>Buy batches</th><th>Deferred-buy decision closes</th><th>Cash clips</th><th>Preflight halvings</th><th>Boundary pending orders</th></tr>'+d.runs.map(r=>`<tr><td>${d.names[r.case]}</td><td>${num(r.financing_usd)}</td><td>${r.debt_calendar_days}</td><td>${r.sell_batches}</td><td>${r.buy_batches}</td><td>${r.wait_sessions}</td><td>${r.cash_clips}</td><td>${r.margin_deferrals}</td><td>${r.pending_orders}</td></tr>`).join('');"""
    s=s.replace('Hosted research project</a>','Hosted research project</a> · <a href="https://www.quantconnect.com/strategies/504/">Original by sanchari</a>')
    return s.replace('full();years();</script>',add+'full();years();</script>')
if __name__=='__main__':build()
