"""Explicit checker-only recovery; never retries the failed financial attempt."""
from datetime import datetime,timezone,timedelta
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import pandas as pd
import numpy as np
from research.studies.spy import risk_gate_study as study
from research.evaluation.control_parity import compare
from research.evaluation.leverage_audit import reconcile
from reporting.temporal import analyze_temporal
from research.evaluation.risk_gate_analysis import independent_temporal
from scripts.recursive_research_review import inspect,verify_artifacts

ORIGINAL=study.PLAN
RECOVERY=Path('research/plans/current/spy-risk-gate-development-v1.recovery.json')
EXTRA=('research/studies/spy/risk_gate_recovery.py','tests/current/test_risk_gate_recovery.py','tests/test_temporal_flat_window.py')
study.CODE=(*study.CODE,*EXTRA)


def eligible(state,original,now):
    if state['status']!='stopped_checker_repaired_not_rerun' or state['actual_financial_attempts']!=1:
        raise ValueError('Expected exactly one stopped failed attempt.')
    if state['attempts'][0]['id']!='5_hold' or state['attempts'][0]['status']!='failed':
        raise ValueError('Preserve the failed first attempt.')
    if len(state['attempts'])!=12 or any(a['status']!='not_started_due_stop' for a in state['attempts'][1:]):
        raise ValueError('Only eleven never-started cases are eligible.')
    deadline=datetime.fromisoformat(state['started_utc'])+timedelta(seconds=original['wall_seconds'])
    remaining=(deadline-now).total_seconds()
    if remaining<=0:raise ValueError('Original study deadline expired; no extension.')
    return deadline,remaining


def prepare():
    if RECOVERY.exists():raise ValueError('Recovery identity already frozen; no retry.')
    original=json.loads(ORIGINAL.read_text()); state=json.loads(study.STATE.read_text())
    deadline,_=eligible(state,original,datetime.now(timezone.utc))
    for f in ('research/policies/risk_gate.py','research/evaluation/leveraged_spy.py','research/evaluation/leverage_audit.py','research/evaluation/risk_gate_analysis.py','research/policies/daily_signals.py'):
        if study.digest(f)!=original['code_hashes'][f]:raise ValueError('Trading/accounting/analysis rules changed; checker-only recovery forbidden.')
    p={**original,'code_hashes':{f:study.digest(f) for f in study.CODE}}
    design,data,_,dividends=study.validate(p)
    source=Path(state['output']); verify_artifacts(source)
    folder=source/'5_hold'; frame=data['hold']
    curve=pd.read_csv(folder/'ledger.csv',index_col='date');trades=pd.read_csv(folder/'trades.csv')
    study.validate_financial_outputs(frame,curve,trades)
    audit=reconcile(frame,dividends,curve,trades,'trend',1,study.FinancingModel(**p['model']))
    old=Path('reports/leverage/3aba31cfafe4da76/base_6pct_buy_hold_1x')
    parity=compare(pd.read_csv(old/'ledger.csv',index_col='date'),curve,pd.read_csv(old/'trades.csv'),trades)
    review=inspect(folder)
    eq=pd.Series(np.r_[300000,curve.equity_usd],index=pd.to_datetime(['2004-12-31',*curve.index]))
    temporal,table=analyze_temporal(eq,initial_capital=300000)
    ta=independent_temporal(eq,temporal,table)
    qualification=dict(kind='read-only qualification, not financial retry; original process remains failed',
                       source=str(folder),source_manifest_sha256=study.digest(source/'manifest.json'),audit=audit,parity=parity,
                       financial_metric_checks=len(review['metric_checks']),temporal_audit=ta,temporal_version=temporal['method_version'])
    p['recovery']=dict(original_plan_sha256=study.digest(ORIGINAL),original_output=str(source),
                       original_failure_sha256=study.digest(source/'failure.json'),original_deadline_utc=deadline.isoformat(),
                       new_case_indices=list(range(1,12)),failed_attempts_counted=1,financial_retries=0,
                       reason='Verified schema-only stop resolved by explicit parity checker; temporal reporting variance correction; trading/accounting rules unchanged.',
                       qualification=qualification)
    study.write(RECOVERY,p);return p


def execute(p):
    state=json.loads(study.STATE.read_text()); original=json.loads(ORIGINAL.read_text())
    deadline,remaining=eligible(state,original,datetime.now(timezone.utc))
    if p['recovery']['original_deadline_utc']!=deadline.isoformat() or p['recovery']['new_case_indices']!=list(range(1,12)):
        raise ValueError('Changed recovery bounds.')
    study.validate(p)
    verify_artifacts(Path(p['recovery']['original_output']))
    if study.digest(ORIGINAL)!=p['recovery']['original_plan_sha256']:raise ValueError('Original plan changed.')
    out=Path('reports/current-risk-gate')/study.digest(RECOVERY)[:16]
    out.mkdir(parents=True,exist_ok=False)
    study.write(out/'state-before-recovery.json',state);study.write(out/'plan.json',p)
    state.update(status='recovery_running',plan_sha256=study.digest(RECOVERY),output=str(out),
                 recovery_plan=str(RECOVERY),original_output=p['recovery']['original_output'],
                 recovery_started_utc=datetime.now(timezone.utc).isoformat(),deadline_utc=deadline.isoformat())
    study.write(study.STATE,state)
    monotonic_deadline=time.monotonic()+remaining;results=[]
    for i in p['recovery']['new_case_indices']:
        remaining=monotonic_deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Original deadline reached; no new case.')
        c=p['cases'][i]
        state['attempts'][i]['status']='running';state['actual_financial_attempts']+=1
        study.write(study.STATE,state)
        try:
            child=subprocess.run([sys.executable,'-m','research.studies.spy.risk_gate_recovery','--case',str(i),'--output',str(out)],capture_output=True,text=True,timeout=remaining)
            (out/(c['id']+'.log')).write_text(child.stdout+child.stderr)
            if child.returncode:raise RuntimeError(f'{c["id"]} failed exit {child.returncode}')
            results.append(json.loads(child.stdout));state['attempts'][i]['status']='completed'
        except (subprocess.TimeoutExpired,RuntimeError) as error:
            state['attempts'][i].update(status='failed',error=str(error));state['failed_attempts']+=1
            state['status']='recovery_failed_no_further_launch';study.write(study.STATE,state)
            study.write(out/'failure.json',state);raise
        study.write(study.STATE,state)
    state.update(status='twelve_attempts_accounting_qualified_pending_review',unstarted_cases=0,
                 completed_processes=11,qualified_original_failed_control=True,finished_utc=datetime.now(timezone.utc).isoformat())
    study.write(study.STATE,state);study.write(out/'case-results.json',results)
    study.write(out/'manifest.json',dict(status=state['status'],artifact_hashes={str(f.relative_to(out)):study.digest(f) for f in sorted(out.rglob('*')) if f.is_file()}))
    print(str(out))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--execute',action='store_true')
    parser.add_argument('--case',type=int);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.freeze:prepare();print(str(RECOVERY));return
    p=json.loads(RECOVERY.read_text());study.PLAN=RECOVERY
    if args.case is not None:
        if args.case not in p['recovery']['new_case_indices']:raise ValueError('Failed case retry forbidden.')
        print(json.dumps(study.case(p,args.case,args.output),allow_nan=False));return
    if args.execute:execute(p)
    else:study.validate(p);print('Recovery preflight passed; no new financial case.')

if __name__=='__main__':main()
