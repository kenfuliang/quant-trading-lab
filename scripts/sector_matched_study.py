"""New counted study; preparation/reservation/evidence never dispatches browser runs."""
import ast, hashlib, json, sys, subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'.local/sector-matched-v1'
PLAN=ROOT/'research/plans/sector-matched-v1.json'


def probe_source():
    tree=ast.parse((ROOT/'.local/stock-risk-v1/original-source.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SelectionComparison')
    methods=[n for n in ast.parse((ROOT/'research/quantconnect/sector_resolution_probe.py').read_text()).body if isinstance(n,ast.FunctionDef)]
    names={n.name for n in methods};cls.body=[n for n in cls.body if not(isinstance(n,ast.FunctionDef) and n.name in names)]+methods
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
    init.body+=ast.parse('self._sector_probe_initialize()').body
    selector=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='select_universe')
    selector.body.insert(-1,ast.parse('self._sector_probe_capture(large)').body[0])
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'


def prepare():
    RAW.mkdir(exist_ok=False);source=probe_source();(RAW/'probe-source.py').write_text(source)
    now=datetime.now(timezone.utc)
    plan=dict(study_id='sector-matched-v1',stage='diagnostic-active',created_utc=now.isoformat(),deadline_utc=(now+timedelta(minutes=90)).isoformat(),max_total_attempts=6,max_diagnostic_cases=1,max_financial_cases=3,technical_retries=2,cases=['original','sector','matched'],dates=['2020-01-01','2025-12-31'],capital_usd=10000,costs='Same25bp native IB fees, staged MOO,90%base, flat6%debit ACT/360 and zero credit interest',resolution_gate='Order-free historical primary sector vs historical industry/group/SIC and security field investigation; freeze evidence and effective/available dates before financial cases. Never fill using future/current labels. Unresolved material classifications block financial stage.',control='Same original top five; each month equal-scale every original weight to sector-treatment total target exposure, computed causally from that same month classification. Exact target exposure match; actual closing exposure may differ through returns, fees and whole-share rounding. No hindsight matching to realized exposures.',sector='Retain36%NAV sector target pro-rata, no replacements or redistribution; no traffic-light gate',hypothesis='Does sector allocation improve DD, Sharpe, Calmar and temporal recovery against equal-stock weights at the same monthly target exposure? Report CAGR/wealth tradeoffs; no parameter tuning.',stops='Six hosted attempts or90minutes; one diagnostic case plus three financial cases and at most two technical retries. Stop financial stage on unresolved required classification, causal timestamps, changed cohort or failed integrity. Preserve negative evidence.',limits=['Viewed development history, not independent OOS','Target-matched control is not realized exposure matching','USD10000fixture, not300000 qualification','No paid sources, agents, broker/account/order operations, services, imports, commits or publication'],source_hashes={'probe':hashlib.sha256(source.encode()).hexdigest()},git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    PLAN.write_text(json.dumps(plan,indent=2)+'\n')
    (RAW/'attempts.json').write_text(json.dumps(dict(study_id=plan['study_id'],status='diagnostic-active',deadline_utc=plan['deadline_utc'],source_hashes=plan['source_hashes'],attempts=[]),indent=2)+'\n')
    print('New stage diagnostic-only; ceiling6attempts, deadline',plan['deadline_utc'])


def reserve(case,retry=False):
    path=RAW/'attempts.json';d=json.loads(path.read_text());now=datetime.now(timezone.utc)
    if d['status'] not in ('diagnostic-active','financial-active') or len(d['attempts'])>=6 or now>=datetime.fromisoformat(d['deadline_utc']):raise ValueError('Closed/cap/deadline prevents launch')
    if case!='probe' and d['status']!='financial-active':raise ValueError('Classification qualification blocks financial stage')
    same=[a for a in d['attempts'] if a['case']==case]
    if bool(same)!=retry:raise ValueError('Duplicate dispatch or retry without failure')
    if retry and (not same[-1]['status'].startswith('failed') or sum(a['retry'] for a in d['attempts'])>=2):raise ValueError('Technical retry not qualified')
    digest=hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()
    if digest!=d['source_hashes'][case]:raise ValueError('Source changed')
    row=dict(case=case,retry=retry,attempt=len(d['attempts'])+1,status='reserved',source_sha256=digest,reserved_utc=now.isoformat());d['attempts'].append(row);path.write_text(json.dumps(d,indent=2)+'\n');print(row)


def decode(texts,case):
    groups={}
    for line in texts:
        if 'SCM|' not in line:continue
        _,c,i,n,h,text=line[line.index('SCM|'):].split('|',5)
        if c!=case:continue
        group=groups.setdefault((int(n),h),{})
        if int(i) in group and group[int(i)]!=text:raise ValueError('Conflicting fragment')
        group[int(i)]=text
    if len(groups)!=1:raise ValueError('Missing/ambiguous packet')
    (total,digest),parts=next(iter(groups.items()))
    if set(parts)!=set(range(total)):raise ValueError('Missing fragment')
    text=''.join(parts[i] for i in range(total))
    if hashlib.sha256(text.encode()).hexdigest()[:12]!=digest:raise ValueError('Truncated/corrupted packet')
    result=json.loads(text)
    if result['case']!=case or result['study']!='sector-matched-v1':raise ValueError('Identity mismatch')
    return result


def record(case):
    import re
    result=decode(json.loads((RAW/f'{case}-terminal-fragments.json').read_text()),case)
    engine=json.loads((RAW/f'{case}-engine-evidence.json').read_text())
    starts=[s for s in engine if 'Launching analysis for' in s]
    assert len(starts)==1
    run=re.search(r'Launching analysis for ([a-f0-9]{32}) ',starts[0])[1]
    assert any(run in s and 'completed in' in s for s in engine)
    if case=='probe':
        assert result['decisions']==72 and result['orders']==0 and result['nav']==10000
        assert not any(result[k] for k in ('future','invalid','unordered'))
    else:
        f=result['full'];assert f['n']==1508 and len(result['months'])==72
        assert not any(f[k] for k in ('rejects','other_fills','pending_orders','feature_future','feature_invalid','feature_unordered'))
        assert abs(result['residual_usd'])<=.1
    d=json.loads((RAW/'attempts.json').read_text());pending=[a for a in d['attempts'] if a['case']==case and a['status']=='reserved'];assert len(pending)==1
    assert pending[0]['source_sha256']==hashlib.sha256((RAW/f'{case}-source.py').read_bytes()).hexdigest()
    pending[0].update(status='completed-verified',backtest_id=run)
    (RAW/'attempts.json').write_text(json.dumps(d,indent=2)+'\n');(RAW/f'{case}-packet.json').write_text(json.dumps(result,indent=2)+'\n');print(case,run,'records',len(result.get('rows',result.get('months',[]))))


def financial_source(case):
    if case not in ('original','sector','matched'):raise ValueError('Not a fixed case')
    tree=ast.parse((ROOT/'.local/stock-risk-v1/original-source.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SelectionComparison')
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and n.value=='stock-risk-v1':n.value='sector-matched-v1'
        if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('RSG|'):n.value=n.value.replace('RSG|','SCM|',1)
    next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AUDIT_CASE' for t in n.targets)).value=ast.Constant(case)
    pure=ast.parse((ROOT/'research/sector_resolution.py').read_text())
    tree.body[:0]=[n for n in pure.body if isinstance(n,(ast.Assign,ast.FunctionDef))]+ast.parse('CASE_MODE='+repr(case)+'\nSECTOR_FALLBACKS='+repr(json.loads((ROOT/'research/plans/sector-matched-v1.classifications.json').read_text())['rows'])).body
    policy=next(n for n in ast.parse((ROOT/'research/quantconnect/sector_matched_policy.py').read_text()).body if isinstance(n,ast.FunctionDef))
    cls.body=[n for n in cls.body if not(isinstance(n,ast.FunctionDef) and n.name=='_risk_monthly')]+[policy]
    capture=next(n for n in ast.parse((ROOT/'research/quantconnect/sector_resolution_probe.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_sector_probe_capture');capture.name='_sector_capture';cls.body.append(capture)
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
    init.body+=ast.parse('self._sector_details={}\nself._target_hash=hashlib.sha256()\nself._resolved_n=0').body
    selector=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='select_universe')
    selector.body=[n for n in selector.body if not(isinstance(n,ast.For) and '_risk_sectors' in ast.unparse(n))]
    selector.body.insert(-1,ast.parse('self._sector_capture(large)').body[0])
    finish=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_risk_finish')
    index=next(i for i,n in enumerate(finish.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='plain' for t in n.targets))
    finish.body[index:index]=ast.parse("package.update(target_sha256=self._target_hash.hexdigest(),resolved_n=self._resolved_n)").body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'


def freeze_financial():
    audit=json.loads((RAW/'classification-audit.json').read_text())
    assert audit['resolved_observations']==27 and audit['remaining']==0
    plan=json.loads(PLAN.read_text());ledger=json.loads((RAW/'attempts.json').read_text())
    assert ledger['status']=='diagnostic-active'
    assert len([a for a in ledger['attempts'] if a['case']=='probe' and a['status']=='completed-verified'])==1
    for case in plan['cases']:
        p=RAW/f'{case}-source.py';p.write_text(financial_source(case));plan['source_hashes'][case]=hashlib.sha256(p.read_bytes()).hexdigest()
    plan.update(stage='financial-active',classification_status='conditional public-filing research inference, not recovered vendor classification',classification_registry='research/plans/sector-matched-v1.classifications.json',classification_registry_sha256=audit['registry_sha256'],qualification=audit['status'],primary_estimand='Sector minus matched-control full-period Calmar, with raw CAGR/DD/UW/wealth tradeoffs; no hidden return threshold or tuning',case_identity='Original five and eligibility fixed; sector and matched total monthly target hashes must be equal; original control must reproduce stock-risk-v1 financial metrics',export='Same readable checksummed compact derived packet; full security IDs/contributions and72monthly top-five decisions. No new raw vendor price/fundamental export.')
    names=['research/sector_resolution.py','research/quantconnect/sector_matched_policy.py','research/quantconnect/sector_resolution_probe.py','scripts/sector_matched_study.py','research/plans/sector-matched-v1.classifications.json','.local/stock-risk-v1/original-source.py']
    plan['input_hashes']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    ledger.update(status='financial-active',source_hashes=plan['source_hashes']);PLAN.write_text(json.dumps(plan,indent=2)+'\n');(RAW/'attempts.json').write_text(json.dumps(ledger,indent=2)+'\n');print('Frozen three sources after27/27conditional dated resolutions; no thresholds tuned')


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='reserve':reserve(sys.argv[2],'--retry' in sys.argv)
    elif sys.argv[1]=='record':record(sys.argv[2])
    elif sys.argv[1]=='freeze-financial':freeze_financial()
