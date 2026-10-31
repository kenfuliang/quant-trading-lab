"""Validate/render only saved aggregate selection-study summaries."""
import json,hashlib,math,csv
from pathlib import Path
from build_qc504_ablation import PAGE
ROOT=Path(__file__).resolve().parents[1];STUDY='qc-breadth-v1';RAW=ROOT/'.local'/STUDY;OUT=ROOT/'.local/performance'/STUDY
CASES=('asset','momentum','lowvol','spy','t11')
NAMES=dict(asset='Asset-class momentum',momentum='Stock momentum',lowvol='Low-volatility stocks',spy='SPY holding',t11='Funded T11')
def validate(rows,case):
    if not rows or any(r.get('study')!='qc-breadth-v1' or r.get('case')!=case for r in rows):raise ValueError('Wrong study/case')
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
    plan=json.loads((ROOT/f'research/plans/{STUDY}.json').read_text());ledger=json.loads((RAW/'attempts.json').read_text());access=json.loads((RAW/'access-result.json').read_text())
    if access['etf_full_history']!=5 or access['stock_full_history']<5 or access['orders']!=0:raise ValueError('Access not verified')
    runs=[];annual=[];missing=[];engines={}
    for case in CASES:
        selected=[a for a in ledger['attempts'] if a['case']==case and a['status']=='completed-summary-captured']
        if len(selected)!=1 or selected[0]['source_sha256']!=plan['source_hashes'][case]:raise ValueError('Missing matching reserved/completed attempt')
    for case in CASES:
        path=RAW/f'{case}-summary-cells.json'
        if not path.exists():missing.append(case);continue
        if hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()!=plan['source_hashes'][case]:raise ValueError('Source mismatch')
        engines[case]=json.loads((RAW/f'{case}-engine-evidence.json').read_text())
        if len(engines[case])!=2 or 'LEAN Engine v2.5.0.0.18209' not in engines[case][0] or 'completed in' not in engines[case][1]:raise ValueError('Missing engine evidence')
        rows=[json.loads(x) for x in json.loads(path.read_text())];f,ys=validate(rows,case)
        if f['n']!=1508 or f['first']!='2020-01-02' or f['last']!='2025-12-31':raise ValueError('Incomplete study calendar')
        if not math.isclose(sum(y['financing_usd'] for y in ys),f['financing_usd'],abs_tol=1e-8) or f['funding_debit_error']>1e-4:raise ValueError('Funding mismatch')
        if abs(f['pnl_residual_usd'])>2:raise ValueError('Native PnL residual exceeds2USD')
        if case in ('asset','momentum','lowvol') and f['selection_events']!=72:raise ValueError('Monthly selection not observed')
        if case in ('momentum','lowvol') and f['fundamental_valid']<=0:raise ValueError('No fundamentals used')
        f['readiness_note']='Short histories excluded; unfilled selection slots remain cash' if f.get('history_short',0) else 'No short histories reported'
        runs.append(f);annual+=ys
    if len({r['calendar_hash'] for r in runs})>1:raise ValueError('Mismatched sessions')
    prior=json.loads((ROOT/'.local/performance/qc504-funded-v1/comparison.json').read_text());parity={}
    for r in runs:
        if r['case']=='t11':
            b=next(x for x in prior['runs'] if x['case']=='t11');parity={k:r[k]-b[k] for k in ('end','cagr','dd','sharpe','calmar','longest_uw','fills','rejects','financing_usd')}
            if any(abs(x)>1e-8 for x in parity.values()):raise ValueError('T11 control drift')
    files=['scripts/prepare_qc_breadth.py','scripts/qc_breadth_budget.py','scripts/parse_qc_breadth_fragments.py','scripts/build_qc_breadth.py','scripts/build_qc504_ablation.py','research/quantconnect/selection_candidates.py','research/quantconnect/selection_access_probe.py','research/quantconnect/qc504_funded_policy.py','research/quantconnect/sector_metrics.py',f'research/plans/{STUDY}.json','tests/test_qc_selection.py']
    evidence=dict(study_id=STUDY,status='complete' if not missing else 'partial',interpretation_status='provisional development comparison with short-history cash periods; not exact source reproduction',missing=missing,attempts=ledger['attempts'],git_sha=ledger['git_sha'],engine_evidence=engines,access_probe=access,t11_control_parity=parity,closed_utc=ledger.get('closed_utc'),unused_repair_slots=ledger.get('unused_repair_slots'),validation=dict(offline_check='make check exit0;304 tests and docs/dependencies passed',source_restoration=json.loads((RAW/'source-restoration.json').read_text()),browser_check=json.loads((RAW/'browser-check.json').read_text())),access_plan_observation='Account project page displayed FREE; successful order-free historical probe and completed allocation runs',intake=json.loads((RAW/'intake/sources.json').read_text()),failed_acceptance=[r['case'] for r in runs if r['rejects'] or not r['fills']],source_hashes=plan['source_hashes'],code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(RAW.glob('*summary-cells.json'))+list(RAW.glob('*terminal-fragments.json'))+list(RAW.glob('*engine-evidence.json'))+list(RAW.glob('*failed-terminal.json'))+[RAW/'access-result.json',RAW/'attempts.json',RAW/'source-restoration.json',RAW/'final-check.log',RAW/'browser-check.json']},checks=['Complete checksummed summaries','Matching1508session calendar','Annual/full NAV compounding, Sharpe moments, Calmar and underwater totals','Common funding model and same-step debit reconciliation','T11 reproduces prior financial metrics','Actual historical fundamentals and feature readiness observed'],limits=['Source-informed adaptations, not exact legacy-code reproduction','Previously viewed development years; no untouched OOS alpha','Whole-share USD10000 model; USD300000 capacity not tested','Native PnL summary is not an independent fill/cash reconstruction','Adjusted/split/dividend handling supplied by hosted engine; raw input snapshots not independently frozen','Universe choices differ between methods; no same-universe attribution control','All three new methods report minimum ready count zero; incomplete-window selections stayed cash; exact dates/reasons need separate diagnosis','Funded staging delays and90pct budget alter original implementation','6pct flat debit ACT/360,zero credit interest; embedded ETF leverage remains in prices','Reported drawdown is daily closing equity, not intraday loss bound'])
    data=dict(names=NAMES,runs=runs,annual=annual,evidence=evidence);OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
    with (OUT/'annual.csv').open('w') as fp:
        w=csv.DictWriter(fp,fieldnames=['case','year','ret','dd','sharpe','annual_calmar','global_uw','n','longest_uw','financing_usd','end'],extrasaction='ignore');w.writeheader();w.writerows(annual)
    s=PAGE.replace('504 · sleeve ablation','Selection · five-case comparison').replace('Frozen full-budget ablation · Five cases, maximum seven attempts (reporting amendment)','Frozen selection adaptations · Five financial cases + one order-free access probe · At most eight total attempts').replace('Do four sleeves improve the tradeoff?','Do different selection rules improve the tradeoff?')
    s=s.replace("cs=['ensemble','t10','t11','s2','s3']","cs=['asset','momentum','lowvol','spy','t11']")
    s=s.replace('original IB margin/fee defaults · unchanged signal and MOO order policy. Standalone sleeves receive the full budget; ensemble retains four quarter budgets.','native IB margin/fees ·90% target · common staged MOO execution ·6% debit ACT/360 · zero credit interest.')
    s=s.replace('Financing, embedded leverage, independent accounting and capacity remain unqualified. Rejected-order cases are conditional. Equal allocation budgets do not mean equal risk.','Article-intended adaptations: percentage momentum, return volatility and true market cap. Legacy source code differs. Independent accounting, capacity and unseen performance remain unqualified; equal budgets do not equalize risk.')
    s=s.replace('Frozen copied source → ensemble + four standalone sleeves → matched metrics → tradeoffs, not promotion','Historical ETF/fundamental inputs → monthly selection at completed close → shared staged MOO execution → matched annual and temporal metrics')
    s=s.replace('Five complete summaries · all four standalone sleeves have rejected orders and are conditional; ensemble has zero. Sorting is descriptive.','Five complete summaries. Check rejection/financing evidence and method differences before interpreting ranks.')
    s=s.replace('Standalone allocation uses full capital, not a 25% sleeve plus 75% cash. This is not realized inside-ensemble attribution.','Stock universes are selected using historical fundamental data. This is not a backtest of today’s500constituents. SPY is an entry-only90% target; selection methods reset their intent monthly; T11 retains its original signals.')
    s=s.replace('Native-book P&L residual is not an independent reconstruction of cash/fills/dividends.','Native P&L plus financing residual is not an independent reconstruction of cash/fills/dividends. Fixed fees and whole shares make capital scale relevant.')
    s=s.replace('<h2>How to interpret this</h2>','<h2>Interpretation limits</h2><p class="warn">Source-informed adaptations; short feature histories are excluded and missing selection slots stay cash. ETF/stock universes differ. No exposure-matched or same-universe attribution control was run. These are previously viewed development years, not independent alpha.</p><h2>How to interpret this</h2>')
    s=s.replace('<h2>Time underwater</h2>','<h2>Data access, selection and funding</h2><p id="access"></p><div class="scroll"><table id="inputs"></table></div><h2>Time underwater</h2>')
    add="""document.getElementById('access').textContent=`Free-account order-free probe: ${d.evidence.access_probe.selected} historical stock constituents; ${d.evidence.access_probe.etf_full_history} ETFs and ${d.evidence.access_probe.stock_full_history} stocks with253completed history bars. Actual stock runs also record fundamental calls and feature readiness.`;document.getElementById('inputs').innerHTML='<tr><th>Case</th><th>Universe calls</th><th>Monthly decisions</th><th>Minimum ready</th><th>Short histories</th><th>Financing USD</th><th>Pending orders</th></tr>'+d.runs.map(r=>`<tr><td>${d.names[r.case]}</td><td>${r.universe_calls??'—'}</td><td>${r.selection_events??'—'}</td><td>${r.min_ready??'—'}</td><td>${r.history_short??'—'}</td><td>${num(r.financing_usd)}</td><td>${r.pending_orders}</td></tr>`).join('');"""
    s=s.replace('<h2>Overall comparison</h2>','<p class="small">Eight hosted attempts: five selected cases, one order-free access probe, one superseded stock run and one failed low-volatility run. Both technical retry slots consumed; study closed.</p><h2>Overall comparison</h2>')
    s=s.replace('full();years();</script>',add+'full();years();</script>')
    (OUT/'index.html').write_text(s.replace('PAYLOAD',json.dumps(data).replace('</','<\\/')))
    (ROOT/'docs/tasks/evidence/2026-10-26-qc-selection-comparison.json').write_text(json.dumps(evidence,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n')
    print(json.dumps(dict(runs=runs,missing=missing),indent=2))
if __name__=='__main__':build()
