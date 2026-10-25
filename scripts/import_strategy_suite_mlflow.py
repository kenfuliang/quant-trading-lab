#!/usr/bin/env python3
"""Import audited strategy-suite cases once into the local MLflow service."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

import pandas as pd
from mlflow import MlflowClient
from mlflow.entities import Metric

ROOT = Path(__file__).resolve().parents[1]


def main(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    audits = manifest.get('audits', {})
    if manifest['status'] != 'completed' or not audits or not all(a.get('passed', False) for a in audits.values()):
        raise ValueError('A completed, independently reconciled suite is required')
    client = MlflowClient(tracking_uri='http://127.0.0.1:5050')
    count = len({c['strategy_id'] for c in manifest['cases']})
    name = f'SPY strategy catalogue research · {count} strategies'
    experiment = client.get_experiment_by_name(name)
    eid = experiment.experiment_id if experiment else client.create_experiment(name)
    registry = {'experiment_id': eid, 'runs': []}
    mapping = {'cagr_pct': 'return_pct', 'total_return_pct': 'total_return_pct', 'max_drawdown_pct': 'drawdown_pct',
               'calmar_full_period': 'calmar', 'sharpe_zero_rf': 'sharpe', 'ending_equity': 'ending_equity',
               'financing_usd': 'financing_usd', 'commission_usd': 'commission_usd', 'slippage_usd': 'slippage_usd',
               'max_effective_leverage': 'max_leverage', 'min_margin_buffer_pct': 'min_buffer_pct',
               'forced_liquidations': 'liquidations'}
    for case in manifest['cases']:
        fingerprint = manifest['fingerprint'] + ':' + case['key']
        matches = client.search_runs([eid], filter_string=f"tags.import_fingerprint = '{fingerprint}'")
        finished = [run for run in matches if run.info.status == 'FINISHED']
        if finished:
            rid = finished[0].info.run_id
        else:
            rid = client.create_run(eid, tags={'mlflow.runName': case['name'], 'import_fingerprint': fingerprint,
                'strategy_id': str(case['strategy_id']), 'evidence': 'exploratory in-sample offline simulation; no out-of-sample proof',
                'model_contract': 'leverage-v1-suite', 'source_data_sha256': str(manifest.get('source_sha256', 'see manifest'))}).info.run_id
            try:
                for key, value in dict(case['parameters'], nominal_leverage=case['leverage'], strategy_id=case['strategy_id']).items():
                    client.log_param(rid, key, json.dumps(value) if isinstance(value, (dict, list)) else value)
                for target, source in mapping.items():
                    value = case['metrics'].get(source)
                    if value is not None and math.isfinite(float(value)):
                        client.log_metric(rid, target, float(value))
                history = pd.read_csv(Path(case['folder']) / 'equity.csv')
                batch = []
                for step, row in enumerate(history.to_dict('records')):
                    timestamp = int(datetime.fromisoformat(row['date']).replace(tzinfo=timezone.utc).timestamp() * 1000)
                    for metric in ('equity_usd', 'return_pct', 'drawdown_pct'):
                        value = row.get(metric)
                        if value is not None and math.isfinite(float(value)):
                            batch.append(Metric(metric, float(value), timestamp, step))
                    if len(batch) >= 900:
                        client.log_batch(rid, metrics=batch)
                        batch = []
                if batch:
                    client.log_batch(rid, metrics=batch)
                client.log_artifacts(rid, case['folder'], artifact_path='report')
                for filename in ('manifest.json', 'catalogue.json', 'assumptions.md'):
                    if (directory / filename).exists():
                        client.log_artifact(rid, str(directory / filename), artifact_path='provenance')
                client.log_artifact(rid, str(directory / 'scores.csv'), artifact_path='comparison')
                client.set_terminated(rid, 'FINISHED')
            except Exception:
                client.set_terminated(rid, 'FAILED')
                raise
        registry['runs'].append({'key': case['key'], 'run_id': rid})
    destination = ROOT / '.local/performance/strategy-suite' / manifest['fingerprint'][:16]
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'mlflow-runs.json').write_text(json.dumps(registry, indent=2))
    print(json.dumps(registry))
    return registry


if __name__ == '__main__':
    main(sys.argv[1])
