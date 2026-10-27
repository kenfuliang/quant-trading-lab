"""Single-worker reserved study. CLI freeze precedes any financial execution."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from research.studies.spy.bounded_study import digest, _json_scores, validate_financial_outputs
from research.studies.spy.spy_backtest import load_data
from research.policies.risk_gate import CASES, frames
from research.evaluation.leveraged_spy import FinancingModel, simulate, score_rows
from research.evaluation.leverage_audit import reconcile
from reporting.temporal import analyze_temporal
from research.evaluation.risk_gate_analysis import independent_temporal
from research.evaluation.control_parity import compare as compare_controls
from scripts.recursive_research_review import inspect

ROOT=Path(__file__).resolve().parents[3]
DESIGN=Path('research/plans/current/spy-risk-gate-development-v1.design.json')
PLAN=Path('research/plans/current/spy-risk-gate-development-v1.executable.json')
STATE=Path('.local/current-risk-gate/state.json')
CODE=('research/policies/risk_gate.py','research/studies/spy/risk_gate_study.py','research/evaluation/risk_gate_analysis.py',
      'research/evaluation/leveraged_spy.py','research/evaluation/leverage_audit.py','research/studies/spy/bounded_study.py',
      'research/policies/daily_signals.py','research/studies/spy/spy_backtest.py','reporting/temporal.py','reporting/annual.py',
      'scripts/recursive_research_review.py','requirements.txt','requirements.lock.txt',
      'research/leverage-model.md','tests/current/test_risk_gate.py','tests/current/test_risk_gate_analysis.py',
      'tests/current/test_risk_gate_study.py','research/evaluation/control_parity.py','tests/current/test_control_parity.py')


def write(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(_json_scores(value),indent=2,allow_nan=False)+'\n'); temporary.replace(path)


def freeze():
    if PLAN.exists(): raise ValueError('Executable identity already frozen; preserve it.')
    design=json.loads(DESIGN.read_text())
    p=dict(schema='risk-gate-execution-v1',design_path=str(DESIGN),design_sha256=digest(DESIGN),
           code_hashes={f:digest(f) for f in CODE},model=asdict(FinancingModel()),
           cases=[dict(id=f'{cost}_{name}',rule=name,cost_bps=cost) for cost in (5,10) for name in CASES],
           created_utc=datetime.now(timezone.utc).isoformat(),max_cases=12,wall_seconds=900)
    assert design['source']['sha256']==digest(design['source']['path'])
    write(PLAN,p); return p


def validate(p):
    if p['schema']!='risk-gate-execution-v1' or p['max_cases']!=12 or p['wall_seconds']!=900:
        raise ValueError('Unsupported execution bounds.')
    if p['cases']!=[dict(id=f'{cost}_{name}',rule=name,cost_bps=cost) for cost in (5,10) for name in CASES]:
        raise ValueError('Frozen six-rule/two-cost cases required.')
    if p['model']!=asdict(FinancingModel()): raise ValueError('Unexpected model.')
    if p['design_path']!=str(DESIGN) or p['design_sha256']!=digest(DESIGN): raise ValueError('Design changed.')
    if p['code_hashes']!={f:digest(f) for f in CODE}: raise ValueError('Code changed after freeze.')
    d=json.loads(DESIGN.read_text()); source=d['source']
    if digest(source['path'])!=source['sha256']: raise ValueError('Source identity changed.')
    raw,dividends,_=load_data(Path(source['path'])); raw=raw.round(2); raw.index=pd.to_datetime(raw.index)
    if len(raw)!=5535: raise ValueError('Warmup coverage changed.')
    data,timeline=frames(raw)
    for name,f in data.items():
        f=f.loc[source['evaluation_start']:source['evaluation_end']].copy()
        f.index=f.index.strftime('%Y-%m-%d'); data[name]=f
        if len(f)!=5283 or f.index[0]!='2005-01-03' or f.index[-1]!='2025-12-31': raise ValueError('Evaluation coverage changed.')
    timeline=timeline.loc[source['evaluation_start']:source['evaluation_end']].copy()
    timeline.index=timeline.index.strftime('%Y-%m-%d')
    if timeline.isna().any().any(): raise ValueError('Unready evaluation features.')
    return d,data,timeline,dividends


def case(p,index,out):
    d,data,timeline,dividends=validate(p)
    state=json.loads(STATE.read_text()); reservation=state['attempts'][index]
    if reservation['status']!='running' or state['plan_sha256']!=digest(PLAN) or state['output']!=str(out):
        raise ValueError('Missing active reservation.')
    c=p['cases'][index]; folder=out/c['id']; folder.mkdir(exist_ok=False)
    model=FinancingModel(**(p['model']|dict(cost_bps=c['cost_bps'])))
    frame=data[c['rule']]; mode='buy_hold' if c['rule']=='buy_hold_entry_only' else 'trend'
    curve,trades=simulate(frame,dividends,mode,1,model)
    frame.to_csv(folder/'signal.csv'); curve.to_csv(folder/'ledger.csv')
    trades.to_csv(folder/'trades.csv',index=False)
    validate_financial_outputs(frame,curve,trades)
    audit=reconcile(frame,dividends,curve,trades,mode,1,model)
    # Evidence is written before higher-level validation; preserve on any failure.
    frame.to_csv(folder/'signal.csv'); curve.to_csv(folder/'ledger.csv')
    trades.to_csv(folder/'trades.csv',index=False)
    write(folder/'audit.json',audit)
    write(folder/'scores.json',score_rows(curve,model,c['id'],mode,1))
    review=inspect(folder,model.capital)
    write(folder/'independent-metrics.json',review)
    eq=pd.Series(np.r_[model.capital,curve.equity_usd],index=pd.to_datetime(['2004-12-31',*curve.index]))
    summary,table=analyze_temporal(eq,initial_capital=model.capital)
    temporal_audit=independent_temporal(eq,summary,table)
    write(folder/'temporal.json',summary); table.to_csv(folder/'temporal.csv',index_label='date')
    write(folder/'temporal-audit.json',temporal_audit)
    timeline.join(frame[['base_target','intended_target']]).join(curve[['shares','cash','equity_usd']]).to_csv(folder/'timeline.csv',index_label='date')
    parity=None
    if c['cost_bps']==5 and c['rule'] in ('hold','ema'):
        old=Path('reports/strategy-suite/97fc0717512bee9e/s002_1x') if c['rule']=='ema' else Path('reports/leverage/3aba31cfafe4da76/base_6pct_buy_hold_1x')
        oldcurve=pd.read_csv(old/'ledger.csv',index_col='date'); oldtrades=pd.read_csv(old/'trades.csv')
        parity=compare_controls(oldcurve,pd.read_csv(folder/'ledger.csv',index_col='date'),oldtrades,pd.read_csv(folder/'trades.csv'))
        parity['source']=str(old)
        write(folder/'control-parity.json',parity)
    return dict(id=c['id'],audit=audit,independent_metrics=len(review['metric_checks']),temporal_audit=temporal_audit,control_parity=parity)


def reserve(state,p,out):
    if state['attempts'] or state['status']!='implementation': raise ValueError('No retry or duplicate reservation allowed.')
    state.update(status='running',plan_sha256=digest(PLAN),output=str(out),
                 started_utc=datetime.now(timezone.utc).isoformat(),
                 attempts=[dict(id=c['id'],status='reserved') for c in p['cases']])
    return state


def execute(p):
    validate(p)
    out=Path('reports/current-risk-gate')/digest(PLAN)[:16]
    if out.exists(): raise ValueError('Existing evidence is immutable; no automatic rerun.')
    state=reserve(json.loads(STATE.read_text()),p,out)
    write(STATE,state); out.mkdir(parents=True); write(out/'plan.json',p)
    start=time.monotonic(); results=[]
    for i,c in enumerate(p['cases']):
        remaining=p['wall_seconds']-(time.monotonic()-start)
        if remaining<=0:
            state['status']='stopped_timeout'; break
        state['attempts'][i]['status']='running'; write(STATE,state)
        try:
            result=subprocess.run([sys.executable,'-m','research.studies.spy.risk_gate_study','--case',str(i),'--output',str(out)],
                                  timeout=remaining,capture_output=True,text=True)
            (out/(c['id']+'.log')).write_text(result.stdout+result.stderr)
            if result.returncode: raise RuntimeError(f'Case {c["id"]} failed exit {result.returncode}; preserved log.')
            state['attempts'][i]['status']='completed'; results.append(json.loads(result.stdout))
        except (subprocess.TimeoutExpired,RuntimeError) as error:
            state['attempts'][i].update(status='failed',error=str(error)); state['status']='stopped_integrity_or_timeout'
            write(STATE,state); write(out/'failure.json',state); raise
        write(STATE,state)
    else: state['status']='simulations_completed_pending_review'
    state['elapsed_seconds']=time.monotonic()-start; write(STATE,state)
    write(out/'case-results.json',results)
    write(out/'manifest.json',dict(status=state['status'],plan_sha256=digest(PLAN),
          artifact_hashes={str(f.relative_to(out)):digest(f) for f in sorted(out.rglob('*')) if f.is_file()}))
    print(str(out))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--freeze',action='store_true'); parser.add_argument('--execute',action='store_true')
    parser.add_argument('--case',type=int); parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.freeze: freeze(); print(str(PLAN)); return
    p=json.loads(PLAN.read_text())
    if args.case is not None: print(json.dumps(case(p,args.case,args.output),allow_nan=False)); return
    if args.execute: execute(p)
    else: validate(p); print('Preflight passed; no simulations executed.')

if __name__=='__main__': main()
