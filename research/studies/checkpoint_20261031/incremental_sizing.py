"""GRS-C001: one pre-existing continuous-sizing proposal; eight offline paths only."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from research.studies.spy import risk_gate_study as old
from research.studies.spy.risk_gate_ablation import frames as discrete_frames
from research.evaluation.control_parity import compare
from reporting.risk_gate_review import verify_temporal_details
from research.evaluation.saved_review import verify_artifacts

CYCLE='GRS-C001'
DESIGN=Path('research/plans/spy-continuous-cap-development-v1.design.json')
PLAN=Path('research/plans/grs-c001-continuous-sizing-v1.json')
ROOT=Path('.local/grs-c001')
RULES=('ema','half_ema','discrete_ema','continuous_ema')
CASES=[dict(id=f'{cost}bp_{rule}',rule=rule,cost_bps=cost) for cost in (5,10) for rule in RULES]
CODE=tuple(dict.fromkeys((*old.CODE,'research/risk_gate_ablation.py','reporting/risk_gate_review.py','research/incremental_sizing.py','tests/test_incremental_sizing.py')))
REFERENCES={
 '5bp_ema':'reports/risk-gate/97e9d442a8b83201/5_ema',
 '10bp_ema':'reports/risk-gate/b6b57fe7077dff3b/10_ema',
 '5bp_discrete_ema':'reports/risk-gate/449096da9fbe1385/5_ablate_ema',
 '10bp_discrete_ema':'reports/risk-gate/449096da9fbe1385/10_ablate_ema'}


def build_frames(raw):
    existing,timeline=discrete_frames(raw)
    prices=raw.close
    sigma=prices.pct_change(fill_method=None).rolling(20,min_periods=20).std(ddof=1)*math.sqrt(252)
    if not np.isfinite(sigma.iloc[20:]).all():raise ValueError('Invalid ready volatility')
    factor=pd.Series(0.,index=raw.index)
    valid=sigma.gt(0)&sigma.notna()
    factor.loc[valid]=(.20/sigma.loc[valid]).clip(upper=1.)
    factor=factor.shift(1).fillna(0.)
    plain=existing['ema'].copy()
    half=plain.copy();half['intended_target']=half.base_target*.5
    half['allocation_factor']=half.intended_target;half['want_long']=half.intended_target.gt(0)
    continuous=plain.copy();continuous['intended_target']=continuous.base_target*factor
    continuous['allocation_factor']=continuous.intended_target;continuous['want_long']=continuous.intended_target.gt(0)
    frames=dict(ema=plain,half_ema=half,discrete_ema=existing['gate_ema'],continuous_ema=continuous)
    decisions=pd.DataFrame(dict(sigma20=sigma.shift(1),ema_eligible=plain.base_target,continuous_cap=factor,
        continuous_target=continuous.intended_target,discrete_target=existing['gate_ema'].intended_target,
        available_at=pd.Series(raw.index.astype(str),index=raw.index).shift(1),execution_date=raw.index.astype(str)))
    return frames,decisions


def primary_claim(rows):
    checks={}
    for cost in (5,10):
        c,b=rows[f'{cost}bp_continuous_ema'],rows[f'{cost}bp_discrete_ema']
        checks[str(cost)]=dict(shorter_duration=c['duration']<b['duration'],no_deeper_dd=c['drawdown_pct']>=b['drawdown_pct']-1e-8,
            duration_change=c['duration']-b['duration'],dd_improvement_pp=c['drawdown_pct']-b['drawdown_pct'],cagr_change_pp=c['return_pct']-b['return_pct'])
    passed=all(x['shorter_duration'] and x['no_deeper_dd'] for x in checks.values())
    dominated=[]
    for cost in (5,10):
        c,h=rows[f'{cost}bp_continuous_ema'],rows[f'{cost}bp_half_ema']
        no_worse=h['return_pct']>=c['return_pct'] and h['drawdown_pct']>=c['drawdown_pct'] and h['duration']<=c['duration']
        strict=h['return_pct']>c['return_pct'] or h['drawdown_pct']>c['drawdown_pct'] or h['duration']<c['duration']
        dominated.append(bool(no_worse and strict))
    return dict(primary_pass=passed,comparisons=checks,half_ema_dominates_both=all(dominated),
        disposition='provisional-path-improvement-growth-tradeoff-unapproved' if passed and not all(dominated) else 'reject-fixed-primary-claim-keep-incumbent',
        independent_validation=False,incumbent_changed=False)


def freeze():
    if PLAN.exists() or ROOT.exists():raise FileExistsError('Preserve existing cycle')
    d=json.loads(DESIGN.read_text())
    # The source design's wording "99% reserve" is corrected here: allocation .99 means 99% invested budget, 1% sizing reserve.
    parents={str(Path(v).parent) for v in REFERENCES.values()}|{'.local/performance/risk-gate/20261025-epoch-v1'}
    for parent in parents:verify_artifacts(parent)
    if old.digest(d['source']['path'])!=d['source']['sha256']:raise ValueError('Source drift')
    p=dict(cycle=CYCLE,standard='GRS-1.0',status='frozen-before-financial-results',created_utc=datetime.now(timezone.utc).isoformat(),
        design_path=str(DESIGN),design_sha256=old.digest(DESIGN),cases=CASES,max_attempts=8,wall_seconds=900,financial_workers=1,automatic_retries=0,
        source=d['source'],model=asdict(old.FinancingModel()),code_hashes={f:old.digest(f) for f in CODE},
        parent_manifests={f:old.digest(Path(f)/'manifest.json') for f in sorted(parents)},control_paths=REFERENCES,
        golden_standard_sha256=old.digest('docs/research-standard.md'),git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        rule_contract=d['rules'],primary_claim=d['primary_claim'],simplicity_check=d['simplicity_check'],
        corrections=['allocation=.99 means 99% invested budget/1% sizing reserve; original wording preserved, numerical model unchanged'],
        interpretation='One sizing-policy replacement; calibration-free20%volatility parameter from prior proposal. No claim that difference isolates color discretization. All data already viewed.',
        bounds='New eight-case budget only; no retries/variants/downloads/dependencies/services/imports/broker actions/publication; stop on first integrity failure.',
        prior_trials='Original gate and ablation plus robustness and feature studies are cited; all-history trial count not exhaustively reconstructed. Existing design had zero allocated/executed paths.',
        report_policy='Primary failure yields a negative-results lesson, not a successful-algorithm paper; independent validation and accepted growth sacrifice remain absent even on path-screen pass.')
    with PLAN.open('x') as f:json.dump(p,f,indent=2);f.write('\n')
    preflight(p);print(str(PLAN))


def preflight(p):
    if p['cycle']!=CYCLE or p['cases']!=CASES or p['max_attempts']!=8 or p['wall_seconds']!=900 or p['financial_workers']!=1 or p['automatic_retries']!=0:raise ValueError('Frozen bounds changed')
    if p['model']!=asdict(old.FinancingModel()) or old.digest(DESIGN)!=p['design_sha256']:raise ValueError('Design/model drift')
    if p['code_hashes']!={f:old.digest(f) for f in CODE} or old.digest('docs/research-standard.md')!=p['golden_standard_sha256']:raise ValueError('Frozen code/standard drift')
    if old.digest(p['source']['path'])!=p['source']['sha256']:raise ValueError('Source drift')
    for parent,digest in p['parent_manifests'].items():
        if old.digest(Path(parent)/'manifest.json')!=digest:raise ValueError('Parent changed')
        verify_artifacts(parent)
    raw,dividends,_=old.load_data(Path(p['source']['path']));raw=raw.round(2);raw.index=pd.to_datetime(raw.index)
    frames,decisions=build_frames(raw)
    if len(raw)!=5535:raise ValueError('Warmup coverage')
    for k,frame in frames.items():
        frame=frame.loc['2005-01-03':'2025-12-31'].copy();frame.index=frame.index.strftime('%Y-%m-%d');frames[k]=frame
        if len(frame)!=5283 or frame.isna().any().any():raise ValueError('Evaluation coverage')
    decisions=decisions.loc['2005-01-03':'2025-12-31'].copy();decisions.index=decisions.index.strftime('%Y-%m-%d')
    if decisions.isna().any().any() or not (pd.to_datetime(decisions.available_at)<pd.to_datetime(decisions.execution_date)).all():raise ValueError('Decision timing')
    return frames,decisions,dividends


def run_case(p,index):
    frames,decisions,dividends=preflight(p);c=CASES[index]
    state=json.loads((ROOT/'state.json').read_text())
    if state['attempts'][index]['status']!='running' or state['plan_sha256']!=old.digest(PLAN):raise ValueError('Unreserved attempt')
    folder=ROOT/c['id'];folder.mkdir(exist_ok=False)
    frame=frames[c['rule']];model=old.FinancingModel(**(p['model']|dict(cost_bps=c['cost_bps'])))
    curve,trades=old.simulate(frame,dividends,'trend',1,model)
    frame.to_csv(folder/'signal.csv');curve.to_csv(folder/'ledger.csv');trades.to_csv(folder/'trades.csv',index=False)
    decisions.to_csv(folder/'decisions.csv',index_label='date')
    old.validate_financial_outputs(frame,curve,trades)
    old.write(folder/'audit.json',old.reconcile(frame,dividends,curve,trades,'trend',1,model))
    old.write(folder/'scores.json',old.score_rows(curve,model,c['id'],'trend',1))
    review=old.inspect(folder);old.write(folder/'independent-metrics.json',review)
    eq=pd.Series(np.r_[model.capital,curve.equity_usd],index=pd.to_datetime(['2004-12-31',*curve.index]))
    temporal,table=old.analyze_temporal(eq,initial_capital=model.capital)
    audit=old.independent_temporal(eq,temporal,table);audit['details']=verify_temporal_details(eq,temporal)
    old.write(folder/'temporal.json',temporal);table.to_csv(folder/'temporal.csv',index_label='date');old.write(folder/'temporal-audit.json',audit)
    parity=None
    if c['id'] in REFERENCES:
        before=Path(REFERENCES[c['id']]);parity=compare(pd.read_csv(before/'ledger.csv',index_col='date'),pd.read_csv(folder/'ledger.csv',index_col='date'),pd.read_csv(before/'trades.csv'),pd.read_csv(folder/'trades.csv'))
        old.write(folder/'control-parity.json',parity)
    row=dict(case=c['id'],cost_bps=c['cost_bps'],rule=c['rule'],**{k:review['overall'][k] for k in ['return_pct','drawdown_pct','calmar','sharpe','ending_equity_usd','mean_close_exposure','trades','commission_usd','slippage_usd','financing_usd']},
        duration=temporal['longest_underwater_duration_sessions'],duration_days=temporal['longest_underwater_duration_calendar_days'],censored=temporal['longest_underwater_right_censored'],
        accounting=json.loads((folder/'audit.json').read_text()),control_parity=parity,metric_checks=len(review['metric_checks']),temporal_checks=audit['scalar_and_window_checks'])
    old.write(folder/'summary.json',row);return row


def execute(p):
    preflight(p);ROOT.mkdir(parents=True,exist_ok=False);old.write(ROOT/'plan.json',p)
    state=dict(cycle=CYCLE,status='running',actual_attempts=0,plan_sha256=old.digest(PLAN),started_utc=datetime.now(timezone.utc).isoformat(),attempts=[dict(id=c['id'],status='reserved') for c in CASES])
    old.write(ROOT/'state.json',state);start=time.monotonic();rows={}
    try:
        for i,c in enumerate(CASES):
            remaining=p['wall_seconds']-(time.monotonic()-start)
            if remaining<=0:raise TimeoutError('Aggregate deadline')
            state['attempts'][i].update(status='running',reserved_utc=datetime.now(timezone.utc).isoformat());state['actual_attempts']+=1;old.write(ROOT/'state.json',state)
            child=subprocess.run([sys.executable,'-m','research.incremental_sizing','--case',str(i)],capture_output=True,text=True,timeout=remaining)
            (ROOT/(c['id']+'.log')).write_text(child.stdout+child.stderr)
            if child.returncode:raise RuntimeError(c['id']+' failed; no retry')
            rows[c['id']]=json.loads(child.stdout);state['attempts'][i].update(status='completed',finished_utc=datetime.now(timezone.utc).isoformat());old.write(ROOT/'state.json',state)
        decision=primary_claim(rows);old.write(ROOT/'comparison.json',dict(cycle=CYCLE,rows=rows,decision=decision));state.update(status='closed-completed',decision=decision['disposition'])
    except Exception as e:
        for a in state['attempts']:
            if a['status']=='running':a.update(status='failed',error=str(e))
        state.update(status='closed-inconclusive-no-retry',error=str(e));raise
    finally:
        state.update(elapsed_seconds=time.monotonic()-start,closed_utc=datetime.now(timezone.utc).isoformat());old.write(ROOT/'state.json',state)
        old.write(ROOT/'manifest.json',dict(cycle=CYCLE,status=state['status'],artifact_hashes={str(f.relative_to(ROOT)):old.digest(f) for f in sorted(ROOT.rglob('*')) if f.is_file()}))
        print(str(ROOT))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--execute',action='store_true');ap.add_argument('--case',type=int,choices=range(8));a=ap.parse_args()
    if a.freeze:freeze();return
    p=json.loads(PLAN.read_text())
    if a.case is not None:print(json.dumps(run_case(p,a.case),allow_nan=False))
    elif a.execute:execute(p)
    else:preflight(p);print('Preflight passed; zero financial attempts')


if __name__=='__main__':main()
