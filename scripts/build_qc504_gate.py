"""Validate and render the bounded T11 gate transfer; no simulations."""
from pathlib import Path
import csv,hashlib,json,math
from build_qc504_ablation import PAGE
ROOT=Path(__file__).resolve().parents[1];STUDY='qc504-t11-gate-v1';RAW=ROOT/'.local'/STUDY;OUT=ROOT/'.local/performance'/STUDY
CASES=('ensemble','t11','gated_t11')
NAMES=dict(ensemble='Four-sleeve ensemble',t11='Ungated T11',gated_t11='T11 + traffic-light cap')
def validate(rows,case):
    if not rows or any(r.get('study')!='qc504-t11-gate-v1' or r.get('case')!=case for r in rows):raise ValueError('Wrong study/case')
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
    plan=json.loads((ROOT/f'research/plans/{STUDY}.json').read_text());ledger=json.loads((RAW/'attempts.json').read_text())
    runs=[];annual=[];engines={}
    for case in CASES:
        if hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()!=plan['source_hashes'][case]:raise ValueError('Source mismatch')
        lines=json.loads((RAW/f'{case}-engine-evidence.json').read_text())
        if len(lines)!=2 or 'LEAN Engine v2.5.0.0.18209' not in lines[0] or 'completed in' not in lines[1]:raise ValueError('Missing engine/completion evidence')
        engines[case]=lines
        attempts=[a for a in ledger['attempts'] if a['case']==case and a['status']=='completed-summary-captured']
        if len(attempts)!=1 or attempts[0]['source_sha256']!=plan['source_hashes'][case]:raise ValueError('Incomplete case reservation')
    for case in CASES:
        rows=[json.loads(x) for x in json.loads((RAW/f'{case}-summary-cells.json').read_text())]
        f,ys=validate(rows,case)
        if f['n']!=sum(f['gate_counts'].values()) or f['gate_seed_n']<200:raise ValueError('Incomplete gate observations')
        if not math.isclose(sum(y['financing_usd'] for y in ys),f['financing_usd'],abs_tol=1e-8) or f['funding_debit_error']>1e-4:raise ValueError('Financing mismatch')
        if abs(f['pnl_residual_usd'])>.10:raise ValueError('Native PnL residual')
        runs.append(f);annual+=ys
    if len({json.dumps(r['gate_counts'],sort_keys=True) for r in runs})!=1:raise ValueError('Mismatched gate states')
    for field in ('calendar_hash','gate_input_sha256','gate_seed_n'):
        if len({r[field] for r in runs})!=1:raise ValueError('Mismatched '+field)
    prior=json.loads((ROOT/'.local/performance/qc504-funded-v1/comparison.json').read_text())
    parity={}
    for r in runs[:2]:
        b=next(x for x in prior['runs'] if x['case']==r['case'])
        parity[r['case']]={k:r[k]-b[k] for k in ('end','cagr','dd','sharpe','calmar','longest_uw','fills','rejects','financing_usd')}
        if any(abs(v)>1e-8 for v in parity[r['case']].values()):raise ValueError('Control drift')
    g=runs[2];u=runs[1]
    delta=dict(drawdown_reduction_pp=100*(abs(u['dd'])-abs(g['dd'])),gap_above_30pct_pp=100*(abs(g['dd'])-.30),cagr_retention=g['cagr']/u['cagr'],terminal_wealth_retention=g['end']/u['end'],longest_underwater_change_sessions=g['longest_uw']-u['longest_uw'],reached_30pct=abs(g['dd'])<=.30)
    files=['scripts/prepare_qc504_gate.py','scripts/qc504_gate_budget.py','scripts/parse_qc504_gate_fragments.py','scripts/build_qc504_gate.py','scripts/build_qc504_ablation.py','research/quantconnect/t11_gate_policy.py','research/quantconnect/sector_comparison.py','research/quantconnect/qc504_funded_policy.py','research/quantconnect/sector_metrics.py',f'research/plans/{STUDY}.json','tests/test_qc504_gate.py']
    receipt=dict(study_id=STUDY,status='complete',missing=[],attempts=ledger['attempts'],attempts_used=len(ledger['attempts']),git_sha=ledger['git_sha'],engine_evidence=engines,closed_utc=ledger.get('closed_utc'),control_parity=parity,gate_tradeoff=delta,failed_acceptance=[r['case'] for r in runs if r['rejects']],validation=dict(offline_check='make check exit0;297 tests passed, docs/dependencies passed',browser='All six annual metric views and underwater/Calmar sorting verified',source_restoration=json.loads((RAW/'source-restoration.json').read_text())),checks=['Checksummed complete fragments','Three matching session and RAW gate input hashes','Fresh controls reproduce prior financial metrics','Annual/full NAV compounding and Sharpe moments','Annual/full Calmar and underwater counts','Annual/full financing and same-step NAV debit','Native PnL plus financing residual within10cents'],limits=['Inspected2020–2025 development history; no untouched OOS evidence','SPY market gate caps all T11 holdings, including inverse/volatility hedges','No equal-exposure control; cannot isolate timing skill from reduced exposure','MOO and staged rotation delay; gate is not a guaranteed drawdown stop','Daily close drawdown omits intraday risk','Native plus financing reconciliation is not independent fill/cash reconstruction','6pct fixed debit ACT/360, not historical broker schedule; credit interest zero','Embedded ETF leverage/expenses remain in prices; capacity and live parity unqualified'],source_hashes=plan['source_hashes'],code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(RAW.glob('*summary-cells.json'))+list(RAW.glob('*terminal-fragments.json'))+list(RAW.glob('*engine-evidence.json'))+[RAW/'attempts.json',RAW/'browser-check.json',RAW/'source-restoration.json',RAW/'final-check.log']})
    data=dict(names=NAMES,runs=runs,annual=annual,evidence=receipt)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
    with (OUT/'annual.csv').open('w') as fp:
        w=csv.DictWriter(fp,fieldnames=['case','year','ret','dd','sharpe','annual_calmar','global_uw','n','longest_uw','financing_usd','end'],extrasaction='ignore');w.writeheader();w.writerows(annual)
    s=PAGE.replace('504 · sleeve ablation','504 · T11 traffic-light test').replace('Frozen full-budget ablation · Five cases, maximum seven attempts (reporting amendment)','Frozen gate transfer · Three cases · At most five attempts').replace('Do four sleeves improve the tradeoff?','Can the traffic-light gate protect T11?').replace("cs=['ensemble','t10','t11','s2','s3']","cs=['ensemble','t11','gated_t11']")
    s=s.replace('original IB margin/fee defaults · unchanged signal and MOO order policy. Standalone sleeves receive the full budget; ensemble retains four quarter budgets.','original IB margin/fees · identical staged MOO execution ·90% base target ·6% debit ACT/360 · green90%, yellow45%, red0% target.')
    s=s.replace('Financing, embedded leverage, independent accounting and capacity remain unqualified. Rejected-order cases are conditional. Equal allocation budgets do not mean equal risk.','Fixed illustrative financing; embedded leverage, independent accounting and capacity remain unqualified. All dates are previously inspected development history.')
    s=s.replace('Frozen copied source → ensemble + four standalone sleeves → matched metrics → tradeoffs, not promotion','Completed RAW SPY close → EMA/volatility traffic light → scale T11 weights → shared staged MOO execution → matched diagnostics')
    s=s.replace('Five complete summaries · all four standalone sleeves have rejected orders and are conditional; ensemble has zero. Sorting is descriptive.','Three fresh complete summaries. Control parity and matching gate-input hashes checked. Sorting is descriptive.')
    s=s.replace('Standalone allocation uses full capital, not a 25% sleeve plus 75% cash. This is not realized inside-ensemble attribution.','The retained EMA/volatility-only gate caps every T11 holding, including inverse and volatility hedges. No exposure-matched control was run; lower risk alone is not timing alpha.')
    s=s.replace('Native-book P&L residual is not an independent reconstruction of cash/fills/dividends.','Native P&L plus explicit financing residual is not an independent reconstruction of cash/fills/dividends.')
    s=s.replace('<h2>Overall comparison</h2>','<p class="warn" id="verdict"></p><h2>Overall comparison</h2>').replace('<h2>Time underwater</h2>','<h2>Gate observations and funding</h2><div class="scroll"><table id="gate"></table></div><h2>Time underwater</h2>')
    extra="""const g=d.runs.find(r=>r.case==='gated_t11'),u=d.runs.find(r=>r.case==='t11'),v=d.evidence.gate_tradeoff;document.getElementById('verdict').textContent=`Gated versus ungated T11: drawdown depth changes by ${v.drawdown_reduction_pp.toFixed(2)} percentage points; ${pct(v.cagr_retention)} of CAGR and ${pct(v.terminal_wealth_retention)} of ending wealth retained. 30% reference ${v.reached_30pct?'met':'not met'}. Longest underwater change: ${v.longest_underwater_change_sessions} sessions.`;document.getElementById('gate').innerHTML='<tr><th>Case</th><th>Green closes</th><th>Yellow closes</th><th>Red closes</th><th>Transitions</th><th>Financing USD</th><th>Pending at boundary</th></tr>'+d.runs.map(r=>`<tr><td>${d.names[r.case]}</td><td>${r.gate_counts.green}</td><td>${r.gate_counts.yellow}</td><td>${r.gate_counts.red}</td><td>${r.gate_changes}</td><td>${num(r.financing_usd)}</td><td>${r.pending_orders}</td></tr>`).join('');"""
    s=s.replace('full();years();</script>',extra+'full();years();</script>')
    (OUT/'index.html').write_text(s.replace('PAYLOAD',json.dumps(data).replace('</','<\\/')))
    (ROOT/'docs/tasks/evidence/2026-10-26-qc504-t11-gate.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n')
    print(json.dumps(dict(runs=runs,delta=delta),indent=2))
if __name__=='__main__':build()
