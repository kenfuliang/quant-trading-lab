"""Predeclared price-peak component removal, four new cases maximum."""
import argparse,json,sys,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from research.studies.spy import risk_gate_study as study
from research.policies.risk_gate import frames as base_frames,states
from reporting.risk_gate_review import verify_temporal_details
from research.evaluation.saved_review import verify_artifacts

PLAN=Path('research/plans/current/spy-risk-gate-price-peak-ablation-v1.json')
CODE=(*study.CODE,'research/studies/spy/risk_gate_ablation.py','tests/current/test_risk_gate_ablation.py','reporting/risk_gate_review.py','tests/test_risk_gate_review.py','tests/test_temporal_flat_window.py')
CASES=[dict(id=f'{cost}_ablate_{base}',rule=f'gate_{base}',cost_bps=cost) for cost in (5,10) for base in ('hold','ema')]


def frames(raw):
    data,time=base_frames(raw)
    # Features in this timeline are already from the preceding close. Applying
    # the same causal recurrence to that sequence requires no additional shift.
    replacement=states(time[['fast','slow','vol','dd']].assign(dd=0.))
    for column in replacement:time[column]=replacement[column]
    time['price_peak_component_enabled']=False
    for name in ('gate_hold','gate_ema'):
        target=pd.concat([data[name].base_target,time.cap.fillna(0)],axis=1).min(axis=1)
        data[name]['allocation_factor']=target;data[name]['intended_target']=target;data[name]['want_long']=target>0
    return data,time


def validate(p):
    if p['cases']!=CASES or p['max_new_cases']!=4 or p['wall_seconds']!=900:raise ValueError('Four-case ablation bound changed.')
    if p['code_hashes']!={f:study.digest(f) for f in CODE}:raise ValueError('Ablation code changed after freeze.')
    # Reuse strict source, dates and full financial-model validation without
    # changing the original twelve-case validator or its frozen identities.
    original=json.loads(study.PLAN.read_text());carrier={**original,'code_hashes':{f:study.digest(f) for f in study.CODE}}
    d,_,_,dividends=study.validate(carrier)
    for name,sha in p['reference_manifests'].items():
        if study.digest(Path(name)/'manifest.json')!=sha:raise ValueError('Parent evidence changed.')
        verify_artifacts(Path(name))
    raw,_,_=study.load_data(Path(d['source']['path']));raw=raw.round(2);raw.index=pd.to_datetime(raw.index)
    data,timeline=frames(raw)
    for name,f in data.items():
        f=f.loc['2005-01-03':'2025-12-31'].copy();f.index=f.index.strftime('%Y-%m-%d');data[name]=f
        if len(f)!=5283:raise ValueError('Coverage changed.')
    timeline=timeline.loc['2005-01-03':'2025-12-31'].copy();timeline.index=timeline.index.strftime('%Y-%m-%d')
    return data,timeline,dividends


def freeze():
    if PLAN.exists():raise ValueError('No ablation refreeze or retry.')
    s=json.loads(study.STATE.read_text())
    if s['actual_financial_attempts']!=12 or s['status']!='twelve_financial_attempts_pending_review':raise ValueError('Initial study must be accounted for first.')
    parent=Path(s['output']);repair=json.loads(Path(s['recovery2_plan']).read_text())
    refs=[parent,Path(repair['recovery']['ema_source']).parent,Path(repair['recovery']['original_hold_source']).parent]
    t=pd.read_csv(parent/'5_gate_hold/timeline.csv',index_col='date');red=t.state.eq('red')
    motivation=dict(red_sessions=int(red.sum()),red_with_price_drawdown_trigger_without_vol_trigger=int((red&(t.dd<-.2)&(t.vol<.4)).sum()),
                    paired_claim_initial='Both combined gates fail joint downside depth/duration criterion at both costs: duration worsens.',
                    expected_mechanism='Removing expanding-price-peak conditions may shorten time underwater, at the possible expense of deeper loss.',
                    tested_change='Disable all raw-price drawdown entry/recovery conditions only. Keep same EMA50/200,20-session volatility, red40%,yellow25%, recovery35%/20%, five staged confirmations and next-open min cap.',
                    decision='Compare ablation versus combined gate and unchanged own base in each cost context. Report all growth and drawdown costs. No tuning or additional follow-up.',
                    historical_scope='Already viewed development history; exploratory mechanism diagnosis, not independent alpha evidence.')
    p=dict(schema='risk-gate-price-peak-ablation-v1',created_utc=datetime.now(timezone.utc).isoformat(),cases=CASES,max_new_cases=4,aggregate_limit=16,
           wall_seconds=900,financial_workers=1,automatic_retries=0,code_hashes={f:study.digest(f) for f in CODE},
           reference_manifests={str(r):study.digest(r/'manifest.json') for r in refs},motivation=motivation,
           initial_plan_sha256=study.digest(study.PLAN),repair_plan_sha256=study.digest(s['recovery2_plan']),
           financing_model=json.loads(study.PLAN.read_text())['model'],source=json.loads(study.DESIGN.read_text())['source'])
    validate(p);study.write(PLAN,p);print(str(PLAN))


def case(p,index,out):
    data,timeline,dividends=validate(p);s=json.loads(study.STATE.read_text());r=s['followup_attempts'][index]
    if r['status']!='running' or s['followup_plan_sha256']!=study.digest(PLAN) or s['followup_output']!=str(out):raise ValueError('Missing reservation.')
    c=p['cases'][index];folder=out/c['id'];folder.mkdir(exist_ok=False);frame=data[c['rule']]
    model=study.FinancingModel(**(p['financing_model']|dict(cost_bps=c['cost_bps'])))
    curve,trades=study.simulate(frame,dividends,'trend',1,model)
    frame.to_csv(folder/'signal.csv');curve.to_csv(folder/'ledger.csv');trades.to_csv(folder/'trades.csv',index=False)
    study.validate_financial_outputs(frame,curve,trades);audit=study.reconcile(frame,dividends,curve,trades,'trend',1,model)
    study.write(folder/'audit.json',audit);study.write(folder/'scores.json',study.score_rows(curve,model,c['id'],'trend',1))
    review=study.inspect(folder);study.write(folder/'independent-metrics.json',review)
    eq=pd.Series(np.r_[300000,curve.equity_usd],index=pd.to_datetime(['2004-12-31',*curve.index]))
    temporal,table=study.analyze_temporal(eq,initial_capital=300000)
    ta=study.independent_temporal(eq,temporal,table);ta['details']=verify_temporal_details(eq,temporal)
    study.write(folder/'temporal.json',temporal);table.to_csv(folder/'temporal.csv',index_label='date');study.write(folder/'temporal-audit.json',ta)
    timeline.join(frame[['base_target','intended_target']]).join(curve[['shares','cash','equity_usd']]).to_csv(folder/'timeline.csv',index_label='date')
    return dict(id=c['id'],audit=audit,financial_metric_checks=len(review['metric_checks']),temporal_audit=ta)


def execute(p):
    validate(p);s=json.loads(study.STATE.read_text())
    if s['actual_financial_attempts']!=12 or s.get('followup_attempts'):raise ValueError('No repeat follow-up or aggregate budget reset.')
    out=Path('reports/current-risk-gate')/study.digest(PLAN)[:16];out.mkdir(parents=True,exist_ok=False);study.write(out/'plan.json',p)
    s.update(status='followup_running',followup_plan_sha256=study.digest(PLAN),followup_output=str(out),followup_launched=True,
             followup_started_utc=datetime.now(timezone.utc).isoformat(),followup_attempts=[dict(id=c['id'],status='reserved') for c in CASES])
    study.write(study.STATE,s);start=time.monotonic();results=[]
    try:
        for i,c in enumerate(CASES):
            remaining=900-(time.monotonic()-start)
            if remaining<=0:raise TimeoutError('Follow-up deadline expired.')
            s['followup_attempts'][i]['status']='running';s['actual_financial_attempts']+=1
            if s['actual_financial_attempts']>16:raise ValueError('Aggregate budget exceeded.')
            study.write(study.STATE,s)
            child=subprocess.run([sys.executable,'-m','research.studies.spy.risk_gate_ablation','--case',str(i),'--output',str(out)],capture_output=True,text=True,timeout=remaining)
            (out/(c['id']+'.log')).write_text(child.stdout+child.stderr)
            if child.returncode:
                s['followup_attempts'][i]['status']='failed';s['failed_attempts']+=1;raise RuntimeError(c['id']+' failed; stop')
            s['followup_attempts'][i]['status']='completed';results.append(json.loads(child.stdout));study.write(study.STATE,s)
    except Exception as error:
        for attempt in s['followup_attempts']:
            if attempt['status']=='running':
                attempt.update(status='failed',error=str(error));s['failed_attempts']+=1
        s.update(status='followup_failed_no_further_launch',last_error=str(error));study.write(study.STATE,s);study.write(out/'failure.json',s);raise
    s.update(status='sixteen_financial_attempts_pending_final_review',followup_finished_utc=datetime.now(timezone.utc).isoformat(),followup_wall_seconds=time.monotonic()-start,studies=2)
    study.write(study.STATE,s);study.write(out/'case-results.json',results)
    study.write(out/'manifest.json',dict(status=s['status'],artifact_hashes={str(f.relative_to(out)):study.digest(f) for f in sorted(out.rglob('*')) if f.is_file()}))
    print(str(out))


def main():
    a=argparse.ArgumentParser();a.add_argument('--freeze',action='store_true');a.add_argument('--execute',action='store_true');a.add_argument('--case',type=int);a.add_argument('--output',type=Path);args=a.parse_args()
    if args.freeze:freeze();return
    p=json.loads(PLAN.read_text())
    if args.case is not None:
        if args.case not in range(4):raise ValueError('Unknown ablation case.')
        print(json.dumps(case(p,args.case,args.output),allow_nan=False));return
    if args.execute:execute(p)
    else:validate(p);print('Ablation preflight passed; no financial case.')

if __name__=='__main__':main()
