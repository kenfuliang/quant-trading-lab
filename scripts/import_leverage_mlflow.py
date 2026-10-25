#!/usr/bin/env python3
"""Idempotently import eight base financing simulations into a separate experiment."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd
from mlflow import MlflowClient
from mlflow.entities import Metric


def main(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['status']!='completed' or not all(a['passed'] for a in manifest['audits'].values()):
        raise ValueError('A completed reconciled experiment is required.')
    client=MlflowClient(tracking_uri='http://127.0.0.1:5050')
    name='SPY leverage research · daily sizing'
    experiment=client.get_experiment_by_name(name)
    eid=experiment.experiment_id if experiment else client.create_experiment(name)
    registry={'experiment_id':eid,'runs':[]}
    mapping={'cagr_pct':'return_pct','total_return_pct':'total_return_pct','max_drawdown_pct':'drawdown_pct',
             'calmar_full_period':'calmar','sharpe_zero_rf':'sharpe','ending_equity':'ending_equity',
             'financing_usd':'financing_usd','commission_usd':'commission_usd','slippage_usd':'slippage_usd',
             'max_effective_leverage':'max_leverage','min_margin_buffer_pct':'min_buffer_pct','forced_liquidations':'liquidations'}
    for case in manifest['cases']:
        if case['scenario']!='base_6pct':continue
        key=manifest['fingerprint']+':'+case['key']
        found=client.search_runs([eid],filter_string=f"tags.import_fingerprint = '{key}'")
        finished=[r for r in found if r.info.status=='FINISHED']
        if finished:
            rid=finished[0].info.run_id
        else:
            rid=client.create_run(eid,tags={'mlflow.runName':case['name'],'import_fingerprint':key,
                'evidence':'offline portfolio-ledger simulation; independently reconciled; not IBKR validation',
                'mode':case['mode'],'model_contract':'leverage-v1','source_data_sha256':manifest['source_sha256']}).info.run_id
            try:
                for param,value in dict(case['parameters'],nominal_leverage=case['leverage'],sizing='daily next-open 99% of nominal target after costs',period='2005-01-03 to 2025-12-31').items():
                    client.log_param(rid,param,value)
                import math
                for target,source in mapping.items():
                    value=float(case['metrics'][source])
                    if math.isfinite(value):client.log_metric(rid,target,value)
                curve=pd.read_csv(Path(case['folder'])/'equity.csv')
                batch=[]
                for step,row in enumerate(curve.to_dict('records')):
                    timestamp=int(datetime.fromisoformat(row['date']).replace(tzinfo=timezone.utc).timestamp()*1000)
                    for metric in ('equity_usd','return_pct','drawdown_pct'):
                        if math.isfinite(row[metric]):batch.append(Metric(metric,float(row[metric]),timestamp,step))
                    if len(batch)>=900:client.log_batch(rid,metrics=batch);batch=[]
                if batch:client.log_batch(rid,metrics=batch)
                client.log_artifacts(rid,case['folder'],artifact_path='report')
                client.log_artifact(rid,str(directory/'assumptions.md'),artifact_path='provenance')
                client.log_artifact(rid,str(directory/'manifest.json'),artifact_path='provenance')
                client.log_artifact(rid,str(directory/'scores.csv'),artifact_path='comparison')
                client.set_terminated(rid,'FINISHED')
            except Exception:
                client.set_terminated(rid,'FAILED');raise
        registry['runs'].append({'key':case['key'],'run_id':rid})
    destination=Path('.local/performance/leverage')/manifest['fingerprint'][:16]
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'mlflow-runs.json').write_text(json.dumps(registry,indent=2))
    print(json.dumps(registry))


if __name__=='__main__':main(sys.argv[1])
