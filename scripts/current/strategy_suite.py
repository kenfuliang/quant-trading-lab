#!/usr/bin/env python3
"""Run supported catalogue signals under one frozen financial contract."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd

from research.studies.spy.spy_backtest import load_data
from research.evaluation.leveraged_spy import FinancingModel, simulate, score_rows
from research.evaluation.leverage_audit import reconcile
from reporting.annual import score_ranks

SOURCE=ROOT/'reports/spy/20261024-235746-728801'
IDS=(1,2,3,4,5,6,7,8,10,11,12,13,14,15,19,21,31,32,33,34,98,99)
EXPOSURES=(1.,1.25,1.5,2.)
CODE=('research/policies/daily_signals.py','research/strategy_catalogue.json','research/control/catalogue.py',
      'research/evaluation/leveraged_spy.py','research/evaluation/leverage_audit.py','research/leverage-model.md',
      'research/strategy-suite.md','research/daily-strategies.md','research/policies/allocation_overlays.py',
      'research/allocation-strategies.md','research/policies/model_signals.py','research/model-strategies.md','research/policies/overnight_signal.py','research/overnight-strategy.md','scripts/current/strategy_suite.py')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute_case(job):
    key,identifier,label,exposure,frame,dividends,folder,config=job
    folder=Path(folder);folder.mkdir()
    model=FinancingModel(**config)
    try:
        curve,trades=simulate(frame,dividends,'trend',exposure,model)
        audit=reconcile(frame,dividends,curve,trades,'trend',exposure,model)
        name=f'{label} · {exposure:g}×'
        scores=score_rows(curve,model,name,'trend',exposure)
        for row in scores:row.update(strategy_id=identifier,case=key)
        curve.to_csv(folder/'ledger.csv',index_label='date')
        trades.to_csv(folder/'trades.csv',index=False)
        pd.DataFrame(scores[1:]).to_csv(folder/'annual.csv',index=False)
        anchored=pd.concat([pd.Series([model.capital],index=[pd.Timestamp(curve.index[0])-pd.Timedelta(days=1)]),
                            pd.Series(curve.equity_usd.to_numpy(),index=pd.to_datetime(curve.index))])
        history=pd.DataFrame({'equity_usd':anchored,'return_pct':anchored.pct_change().fillna(0)*100,
                              'drawdown_pct':(anchored/anchored.cummax()-1)*100})
        history.loc[anchored<=0,'return_pct']=np.nan
        history.to_csv(folder/'equity.csv',index_label='date')
        (folder/'metrics.json').write_text(json.dumps(scores[0],indent=2))
        from research.policies.daily_signals import DEFINITIONS as D
        from research.policies.allocation_overlays import DEFINITIONS as A
        from research.policies.model_signals import DEFINITIONS as M
        from research.policies.overnight_signal import DEFINITIONS as N
        DEFINITIONS = D | A | M | N
        case={'key':key,'strategy_id':identifier,'name':name,'leverage':exposure,'folder':str(folder.resolve()),
              'metrics':scores[0],'parameters':dict(config,nominal_leverage=exposure,strategy_id=identifier,signal_parameters=DEFINITIONS[identifier][1],strategy_variant=label)}
        return case,audit,scores
    except Exception as error:
        (folder/'failure.json').write_text(json.dumps({'status':'failed','type':type(error).__name__,'message':str(error)}))
        raise


def prepare(workers=3):
    from research.control.catalogue import load_catalogue
    from research.policies.daily_signals import build_signal, DEFINITIONS as D
    from research.policies.allocation_overlays import build_allocation_signal, DEFINITIONS as A
    from research.policies.model_signals import build_model_signal, DEFINITIONS as M
    from research.policies.overnight_signal import build_overnight_signal, DEFINITIONS as N
    DEFINITIONS = D | A | M | N
    catalogue=load_catalogue()
    records={s['id']:s for s in catalogue['strategies']}
    raw,dividends,metadata=load_data(SOURCE/'source-data.json')
    original=json.loads((SOURCE/'manifest.json').read_text())
    raw=raw.round(2)
    raw.index=pd.to_datetime(raw.index)
    if metadata['sha256']!=original['source']['sha256']:raise ValueError('Source snapshot changed.')
    identity={'source_sha256':metadata['sha256'],'model':asdict(FinancingModel()),'strategy_ids':list(IDS),'exposures':EXPOSURES,
              'code_hashes':{name:digest(ROOT/name) for name in CODE}}
    fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    directory=ROOT/'reports/strategy-suite'/fingerprint[:16]
    manifest_path=directory/'manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if manifest['status']!='completed':raise ValueError('Incomplete suite retained: '+str(directory))
        for name,sha in manifest['artifact_hashes'].items():
            if digest(directory/name)!=sha:raise ValueError('Suite artifact hash mismatch: '+name)
        return directory
    if directory.exists():raise ValueError('Incomplete suite directory retained: '+str(directory))
    directory.mkdir(parents=True)
    manifest={'status':'running','fingerprint':fingerprint,**identity,'created_utc':datetime.now(timezone.utc).isoformat(),
              'evaluation':'in-sample exploratory, no independent holdout','cases':[],'audits':{}}
    manifest_path.write_text(json.dumps(manifest,indent=2))
    (directory/'catalogue.json').write_text(json.dumps(catalogue,indent=2))
    (directory/'assumptions.md').write_text((ROOT/'research/strategy-suite.md').read_text()+'\n\n'+(ROOT/'research/leverage-model.md').read_text())
    jobs=[]
    try:
        for identifier in IDS:
            builder = build_signal if identifier in D else (build_allocation_signal if identifier in A else (build_model_signal if identifier in M else build_overnight_signal))
            signal=builder(raw.copy(),identifier)
            if not signal.index.equals(raw.index):raise ValueError('Signal changed source dates.')
            if signal.want_long.isna().any():raise ValueError('Signal contains unknown positions.')
            frame=signal.loc['2005-01-01':'2025-12-31'].copy()
            frame.index=frame.index.strftime('%Y-%m-%d')
            if len(frame)!=5283:raise ValueError('Unexpected suite evaluation coverage.')
            frame.to_csv(directory/f'signal-{identifier:03}.csv',index_label='date')
            for exposure in EXPOSURES:
                key=f's{identifier:03}_{exposure:g}x'
                jobs.append((key,identifier,DEFINITIONS[identifier][0],exposure,frame,dividends,str(directory/key),identity['model']))
        scores=[]
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures=[executor.submit(execute_case,job) for job in jobs]
            for i,future in enumerate(as_completed(futures),1):
                case,audit,rows=future.result()
                manifest['cases'].append(case);manifest['audits'][case['key']]=audit;scores.extend(rows)
                if i%15==0:print(f'Reconciled {i}/{len(jobs)} suite cases.',flush=True)
        manifest['cases'].sort(key=lambda c:(c['strategy_id'],c['leverage']))
        table=pd.DataFrame(scores).sort_values(['strategy_id','exposure','period'])
        for metric in ('calmar','sharpe'):table[metric+'_rank']=table.groupby('period')[metric].transform(score_ranks)
        table.to_csv(directory/'scores.csv',index=False)
        manifest['status']='completed'
        manifest['artifact_hashes']={str(p.relative_to(directory)):digest(p) for p in directory.rglob('*') if p.is_file() and p!=manifest_path}
        manifest_path.write_text(json.dumps(manifest,indent=2))
    except Exception as error:
        manifest['status']='failed';manifest['failure']={'type':type(error).__name__,'message':str(error)}
        manifest_path.write_text(json.dumps(manifest,indent=2));raise
    return directory


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=3);parser.add_argument('--skip-import',action='store_true')
    args=parser.parse_args()
    if not 1<=args.workers<=4:parser.error('workers must be between 1 and 4')
    directory=prepare(args.workers)
    from reporting.strategy_suite import render
    render(directory)
    if not args.skip_import:
        subprocess.run([str(ROOT/'.local/venvs/mlflow/bin/python'),str(ROOT/'scripts/import_strategy_suite_mlflow.py'),str(directory)],cwd=ROOT,check=True)
        render(directory)
    print(directory)


if __name__=='__main__':main()
