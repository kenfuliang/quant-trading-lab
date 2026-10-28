"""Second explicit representation repair. No failed financial case is rerun."""
from datetime import datetime,timezone,timedelta
import argparse,json,subprocess,sys,time
from pathlib import Path
import pandas as pd
from research.studies.spy import risk_gate_recovery as previous
from research.studies.spy import risk_gate_study as study
from research.evaluation.control_parity import compare
from research.evaluation.leverage_audit import reconcile
from research.evaluation.saved_review import verify_artifacts,inspect

PLAN=Path('research/plans/current/spy-risk-gate-development-v1.recovery2.json')
CODE=(*study.CODE,'research/studies/spy/risk_gate_recovery2.py','tests/current/test_risk_gate_recovery2.py')
study.CODE=CODE


def bounds(state,original,now):
    if state['status']!='recovery_failed_no_further_launch' or state['actual_financial_attempts']!=2 or state['failed_attempts']!=2:
        raise ValueError('Expected exactly two stopped representation failures.')
    if len(state['attempts'])!=12 or any(a['status']!='failed' for a in state['attempts'][:2]) or any(a['status']!='not_started_due_stop' for a in state['attempts'][2:]):
        raise ValueError('Only ten never-started cases may run.')
    deadline=datetime.fromisoformat(state['started_utc'])+timedelta(seconds=900)
    if now>=deadline:raise ValueError('Original deadline exhausted; no extension.')
    return deadline


def prepare():
    if PLAN.exists():raise ValueError('No duplicate freeze/retry.')
    original=json.loads(previous.ORIGINAL.read_text());s=json.loads(study.STATE.read_text())
    deadline=bounds(s,original,datetime.now(timezone.utc));source=Path(s['output']);folder=source/'5_ema'
    study.write(source/'manifest.json',dict(status=s['status'],artifact_hashes={str(f.relative_to(source)):study.digest(f) for f in sorted(source.rglob('*')) if f.is_file() and f.name!='manifest.json'}))
    verify_artifacts(source)
    for f in ('research/evaluation/leveraged_spy.py','research/evaluation/leverage_audit.py','research/evaluation/risk_gate_analysis.py','research/policies/daily_signals.py'):
        if study.digest(f)!=original['code_hashes'][f]:raise ValueError('Accounting or financial analysis changed.')
    p={**original,'code_hashes':{f:study.digest(f) for f in CODE}}
    d,frames,timeline,dividends=study.validate(p)
    prior=pd.read_csv(folder/'signal.csv',index_col='date');current=frames['ema']
    pd.testing.assert_frame_equal(prior.drop(columns='allocation_factor'),current.drop(columns='allocation_factor'),check_exact=False,rtol=0,atol=1e-12)
    if not prior.allocation_factor.eq(prior.want_long.astype(float)).all() or not current.allocation_factor.eq(1).all():
        raise ValueError('Unexpected diagnostic correction.')
    raw=pd.read_csv(folder/'ledger.csv',index_col='date');trades=pd.read_csv(folder/'trades.csv')
    study.validate_financial_outputs(prior,raw,trades)
    audit=reconcile(prior,dividends,raw,trades,'trend',1,study.FinancingModel(**p['model']))
    normalized=raw.copy();normalized['effective_target_leverage']=1.
    old=Path('reports/strategy-suite/97fc0717512bee9e/s002_1x')
    parity=compare(pd.read_csv(old/'ledger.csv',index_col='date'),normalized,pd.read_csv(old/'trades.csv'),trades)
    inspect(folder)
    # Hold the gate's historical state/cap/features invariant across this repair.
    oldtime=pd.read_csv(folder/'timeline.csv',index_col='date')
    for col in timeline:
        pd.testing.assert_series_equal(oldtime[col],timeline[col],check_names=False,check_dtype=False,check_exact=False,atol=1e-12,rtol=0)
    p['recovery']=dict(original_plan_sha256=study.digest(previous.ORIGINAL),prior_recovery_sha256=study.digest(previous.RECOVERY),
        original_deadline_utc=deadline.isoformat(),new_case_indices=list(range(2,12)),financial_retries=0,failed_attempts_counted=2,
        original_hold_source=json.loads(previous.RECOVERY.read_text())['recovery']['qualification']['source'],
        ema_source=str(folder),ema_source_manifest_sha256=study.digest(source/'manifest.json'),
        ema_audit=audit,ema_derived_parity=parity,
        ema_representation_correction='Only derived effective_target_leverage becomes nominal 1x; raw CSV remains unchanged. want_long/intended_target, trades and all monetary fields unchanged.',
        unchanged_state_timeline=True,reason='Resolve control budget-versus-desired-target representation; no rule/threshold, cost, simulation or accounting change.')
    study.write(PLAN,p);print(str(PLAN))


def execute(p):
    s=json.loads(study.STATE.read_text());original=json.loads(previous.ORIGINAL.read_text())
    deadline=bounds(s,original,datetime.now(timezone.utc));study.validate(p)
    if p['recovery']['new_case_indices']!=list(range(2,12)) or p['recovery']['original_deadline_utc']!=deadline.isoformat():raise ValueError('Changed bounds.')
    verify_artifacts(Path(p['recovery']['ema_source']).parent)
    out=Path('reports/current-risk-gate')/study.digest(PLAN)[:16];out.mkdir(parents=True,exist_ok=False)
    study.write(out/'state-before-recovery.json',s);study.write(out/'plan.json',p)
    s.update(status='representation_recovery_running',output=str(out),plan_sha256=study.digest(PLAN),recovery2_plan=str(PLAN),deadline_utc=deadline.isoformat())
    study.write(study.STATE,s);limit=time.monotonic()+(deadline-datetime.now(timezone.utc)).total_seconds();results=[]
    try:
        for i in range(2,12):
            remaining=limit-time.monotonic()
            if remaining<=0:raise TimeoutError('Original deadline reached.')
            c=p['cases'][i];s['attempts'][i]['status']='running';s['actual_financial_attempts']+=1;study.write(study.STATE,s)
            child=subprocess.run([sys.executable,'-m','research.studies.spy.risk_gate_recovery2','--case',str(i),'--output',str(out)],capture_output=True,text=True,timeout=remaining)
            (out/(c['id']+'.log')).write_text(child.stdout+child.stderr)
            if child.returncode:
                s['attempts'][i]['status']='failed';s['failed_attempts']+=1;raise RuntimeError(c['id']+' failed; stop')
            results.append(json.loads(child.stdout));s['attempts'][i]['status']='completed';study.write(study.STATE,s)
    except Exception as error:
        for attempt in s['attempts']:
            if attempt['status']=='running':
                attempt.update(status='failed',error=str(error));s['failed_attempts']+=1
        s.update(status='recovery2_failed_no_further_launch',last_error=str(error));study.write(study.STATE,s);study.write(out/'failure.json',s);raise
    s.update(status='twelve_financial_attempts_pending_review',unstarted_cases=0,completed_processes=10,qualified_failed_controls=2,finished_utc=datetime.now(timezone.utc).isoformat())
    study.write(study.STATE,s);study.write(out/'case-results.json',results)
    study.write(out/'manifest.json',dict(status=s['status'],artifact_hashes={str(f.relative_to(out)):study.digest(f) for f in sorted(out.rglob('*')) if f.is_file()}))
    print(str(out))


def main():
    a=argparse.ArgumentParser();a.add_argument('--freeze',action='store_true');a.add_argument('--execute',action='store_true');a.add_argument('--case',type=int);a.add_argument('--output',type=Path);args=a.parse_args()
    if args.freeze:prepare();return
    p=json.loads(PLAN.read_text());study.PLAN=PLAN
    if args.case is not None:
        if args.case not in range(2,12):raise ValueError('Failed control retry forbidden.')
        print(json.dumps(study.case(p,args.case,args.output),allow_nan=False));return
    if args.execute:execute(p)
    else:study.validate(p);print('Representation recovery preflight passed.')

if __name__=='__main__':main()
