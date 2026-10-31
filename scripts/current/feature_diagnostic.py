#!/usr/bin/env python3
"""Bounded feature diagnosis on frozen SPY and existing gate labels, offline."""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import hashlib,json,shutil,sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from research.studies.spy.spy_backtest import load_data
from research.features.feature_engineering import (REGISTRY,FEATURES,BASELINES,VERSION,build_features,
    future_risk,fit_edges,assign_bins,mature_within,rank_association)

PLAN=ROOT/'research/plans/spy-feature-diagnostic-v1.design.json'
CODE=['research/features/feature_engineering.py','scripts/current/feature_diagnostic.py','tests/current/test_feature_engineering.py',
      '.agents/skills/trade-feature-engineering/SKILL.md']
GATE=ROOT/'.local/performance/gate-decisions/20261025-v2'
SOURCE=ROOT/'reports/spy/20261024-235746-728801/source-data.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


def verify(plan):
    if (plan['candidate_ids']!=FEATURES or plan['feature_budget']!=3 or plan['outcome_horizon']!=21
            or plan['selected_pair']!='5_ablate_ema' or plan['stop']['new_financial_simulations']!=0):
        raise ValueError('Fixed three-feature saved-label study only.')
    for rel,h in plan['inputs'].items():
        if sha(ROOT/rel)!=h:raise ValueError('Input identity changed: '+rel)
    manifest=json.loads((GATE/'manifest.json').read_text())
    for rel,h in manifest['artifact_hashes'].items():
        if sha(GATE/rel)!=h:raise ValueError('Saved gate artifact changed: '+rel)
    return len(manifest['artifact_hashes'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    plan=json.loads(PLAN.read_text());verified=verify(plan);out=args.output.resolve()
    if out.exists():raise ValueError('Preserve existing evidence; choose a new output version.')
    out.mkdir(parents=True);(out/'source').mkdir()
    identity=dict(method=VERSION,plan_sha256=sha(PLAN),created_utc=datetime.now(timezone.utc).isoformat(),
        code_hashes={f:sha(ROOT/f) for f in CODE},financial_simulations=0,feature_candidates=3,
        paid_api_calls=0,new_market_snapshots=0,gate_artifacts_verified=verified)
    write(out/'execution.json',identity);shutil.copyfile(PLAN,out/'plan.json')
    for f in CODE:shutil.copyfile(ROOT/f,out/'source'/Path(f).name)
    raw,_,_=load_data(SOURCE);raw=raw.round(2);raw.index=pd.to_datetime(raw.index)
    features=build_features(raw)
    # Future rows and current-session bars must not alter earlier open-time inputs.
    causal_checks=[]
    for k in [300,2000,len(raw)-100]:
        pd.testing.assert_frame_equal(features.iloc[:k],build_features(raw.iloc[:k]))
        perturbed=raw.copy();perturbed.iloc[k:,perturbed.columns.get_indexer(['open','high','low','close'])]*=1.5
        pd.testing.assert_frame_equal(features.iloc[:k+1],build_features(perturbed).iloc[:k+1])
        causal_checks.append(dict(boundary=str(raw.index[k].date()),prefix_and_future_perturbation_pass=True))
    d=pd.read_csv(GATE/plan['selected_pair']/'decisions.csv',parse_dates=['execution_session']).set_index('execution_session')
    o=pd.read_csv(GATE/plan['selected_pair']/'outcomes.csv',parse_dates=['execution_session','label_available_after_close'])
    o=o[o.horizon_sessions==21].set_index('execution_session')
    if not d.index.equals(o.index) or d.index.has_duplicates or len(d)!=5283 or not d.decision_id.equals(o.decision_id):
        raise ValueError('Exact unique decision/label identity join required.')
    f=features.loc[d.index].copy()
    if not np.isfinite(f[FEATURES+BASELINES].to_numpy(float)).all():
        raise ValueError('Unexpected missing/nonfinite evaluation feature.')
    if not pd.DatetimeIndex(pd.to_datetime(d.observed_close)).equals(pd.DatetimeIndex(f.observed_close)):
        raise ValueError('Decision availability/source alignment mismatch.')
    np.testing.assert_allclose(f.sigma20,d.sigma20,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(f.ema_positive,d.base_target)
    # Independent scalar calculations from raw values, including forward target indexing.
    checks=0;close=raw.close.to_numpy();positions=raw.index.get_indexer(d.index)
    risk=future_risk(raw).loc[d.index]
    for i,j in enumerate(positions):
        r20=[close[k]/close[k-1]-1 for k in range(j-20,j)]
        r60=[close[k]/close[k-1]-1 for k in range(j-60,j)]
        assert abs(f.vol_ratio20_60.iloc[i]-np.std(r20,ddof=1)/np.std(r60,ddof=1))<1e-10
        ranges=[(raw.high.iloc[k]-raw.low.iloc[k])/close[k] for k in range(j-20,j)]
        assert abs(f.range20_pct.iloc[i]-sum(ranges)/20)<1e-12;checks+=2
        if j+20<len(raw):
            r=[close[k]/close[k-1]-1 for k in range(j,j+21)]
            assert abs(risk.iloc[i]-np.std(r,ddof=1)*np.sqrt(252))<1e-10;checks+=1
        else:assert pd.isna(risk.iloc[i]);checks+=1
    f.to_csv(out/'features.csv',index_label='execution_session')
    registry=[dict(r,version=VERSION,availability='Previous completed source close; exactly one shift',
        undefined_policy='Warmup null; zero denominator null; invalid OHLC raises',proposal_round=1) for r in REGISTRY]
    write(out/'feature-registry.json',registry)
    joined=f.join(o.drop(columns='decision_id')).join(d[['intended_reduction','reduction_episode_start','warning_already_cash']])
    joined['future_risk21']=risk;joined['stride21']=(np.arange(len(joined))%21)==0
    if not joined.loc[joined.right_censored,'future_risk21'].isna().all():raise ValueError('Risk target censoring mismatch.')
    calibration=f.loc['2005-01-03':'2011-12-31']
    cuts={name:fit_edges(calibration[name]) for name in FEATURES}
    sigma_median=float(calibration.sigma20.median())
    write(out/'calibration.json',dict(period='2005-2011 features only',tercile_edges=cuts,sigma20_median=sigma_median,
        future_periods_not_used_to_fit=True))
    for name in FEATURES:joined[name+'_bin']=assign_bins(joined[name],cuts[name])
    joined['sigma20_stratum']=np.where(joined.sigma20<=sigma_median,'low_sigma20','high_sigma20')
    associations=[];bins=[];redundancy=[];quality=[]
    for name in FEATURES+BASELINES:
        quality.append(dict(feature=name,rows=len(f),missing=int(f[name].isna().sum()),distinct=int(f[name].nunique()),
                            minimum=float(f[name].min()),maximum=float(f[name].max())))
    blocks=[('calibration','2005-01-03','2011-12-31'),('development_2012_2018','2012-01-01','2018-12-31'),('development_2019_2025','2019-01-01','2025-12-31')]
    for block,start,end in blocks:
        data=mature_within(joined,start,end)
        for sampling in ['all_overlapping','fixed_stride21']:
            view=data if sampling=='all_overlapping' else data[data.stride21]
            for name in FEATURES+BASELINES:
                for target in ['base_return','future_risk21','gate_minus_base_pp']:
                    associations.append(dict(block=block,sampling=sampling,feature=name,target=target,
                                             **rank_association(view[name],view[target])))
        for name in FEATURES:
            for ref in FEATURES+BASELINES:
                if name!=ref:redundancy.append(dict(block=block,feature=name,reference=ref,**rank_association(data[name],data[ref])))
            for stratum in ['all','low_sigma20','high_sigma20']:
                view=data if stratum=='all' else data[data.sigma20_stratum==stratum]
                for bucket in ['low','middle','high']:
                    group=view[view[name+'_bin']==bucket]
                    actionable=group[group.intended_reduction]
                    episodes=group[group.reduction_episode_start]
                    bins.append(dict(block=block,feature=name,stratum=stratum,bucket=bucket,n=len(group),
                        mean_future_risk21=None if group.empty else float(group.future_risk21.mean()),
                        mean_base_return_pct=None if group.empty else float(group.base_return.mean()*100),
                        mean_gate_minus_base_pp=None if group.empty else float(group.gate_minus_base_pp.mean()),
                        actionable_sessions=len(actionable),episode_starts=len(episodes),
                        actionable_label_counts={str(k):int(v) for k,v in actionable.label.value_counts().items()},
                        episode_label_counts={str(k):int(v) for k,v in episodes.label.value_counts().items()}))
    pd.DataFrame(associations).to_csv(out/'associations.csv',index=False)
    pd.DataFrame(redundancy).to_csv(out/'redundancy.csv',index=False)
    pd.DataFrame(quality).to_csv(out/'quality.csv',index=False)
    write(out/'bins.json',bins)
    joined.to_csv(out/'joined-outcome-diagnostics.csv',index_label='execution_session')
    write(out/'validation.json',dict(causal_checks=causal_checks,independent_scalar_checks=checks,
        existing_sigma_and_ema_reference_match=True,label_maturity_boundary_filter=True,source_calendar_certified=False,
        feature_candidates=3,proposal_rounds=1,financial_simulations=0))
    body='<h1>SPY feature diagnostic</h1><p>Three fixed features; saved outcomes; no strategy simulation. All history is viewed development. Rank correlations are time-series associations, not cross-sectional IC or alpha.</p>'
    body+='<h2>Feature registry</h2>'+pd.DataFrame(registry)[['id','formula','units','mechanism']].to_html(index=False)
    body+='<h2>Quality</h2>'+pd.DataFrame(quality).to_html(index=False)
    body+='<h2>Later development blocks · fixed nonoverlapping outcome anchors</h2>'+pd.DataFrame([r for r in associations if r['block']!='calibration' and r['sampling']=='fixed_stride21']).to_html(index=False,float_format=lambda x:f'{x:.3f}')
    body+='<h2>Fixed calibration terciles · primary volatility ratio</h2>'+pd.DataFrame([r for r in bins if r['feature']=='vol_ratio20_60' and r['block']!='calibration']).to_html(index=False,float_format=lambda x:f'{x:.4f}')
    body+='<p>Bin risk values are annualized volatility fractions, not probabilities. Gate-label counts condition on a selected policy and overlap; episode counts are small. Within-sigma strata are descriptive, not an incremental-prediction test. No confidence levels or trading rule selected.</p>'
    body+='<p>Downloads: '+ ' · '.join(f'<a href="{x}">{x}</a>' for x in ['features.csv','feature-registry.json','associations.csv','redundancy.csv','bins.json','calibration.json','validation.json','manifest.json'])+'</p>'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>SPY feature diagnostic</title><style>body{font:15px system-ui;color:#24374a;margin:30px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #d9e0e6;padding:8px;text-align:left}h2{margin-top:35px}p{max-width:1000px}a{color:#2459a0}</style>'+body)
    assert verify(plan)==verified
    write(out/'manifest.json',dict(method=VERSION,financial_simulations=0,artifact_hashes={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(output=str(out),feature_candidates=3,rows=len(f),independent_scalar_checks=checks,
                         associations=len(associations),financial_simulations=0)))


if __name__=='__main__':main()
