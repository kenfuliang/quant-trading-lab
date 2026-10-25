#!/usr/bin/env python3
"""Import prepared result artifacts into local MLflow; run with its isolated Python."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from mlflow import MlflowClient
from mlflow.entities import Metric


def main():
    bundle_path = Path(sys.argv[1]).resolve()
    bundle = json.loads(bundle_path.read_text())
    client = MlflowClient(tracking_uri='http://127.0.0.1:5050')
    name = 'SPY saved historical comparisons'
    experiment = client.get_experiment_by_name(name)
    experiment_id = experiment.experiment_id if experiment else client.create_experiment(name)
    registry = {'experiment_id': experiment_id, 'runs': []}
    for item in bundle['runs']:
        fingerprint = bundle['fingerprint'] + ':' + item['mode']
        found = client.search_runs([experiment_id], filter_string=f"tags.import_fingerprint = '{fingerprint}'")
        completed = [r for r in found if r.info.status == 'FINISHED']
        if completed:
            run_id = completed[0].info.run_id
        else:
            run = client.create_run(experiment_id, tags={'mlflow.runName': item['name'], 'import_fingerprint': fingerprint,
                'evidence': 'audited historical simulation; imported, not rerun', 'source_run': bundle['source_run'],
                'strategy': item['mode'], 'source_engine': bundle['source_engine'], 'source_data_sha256': bundle['source_data_sha256']})
            run_id = run.info.run_id
            try:
                for key, value in bundle['parameters'].items():
                    client.log_param(run_id, key, str(value))
                client.log_param(run_id, 'observed_period', '2005-01-03 to 2025-12-31')
                for key, value in item['metrics'].items():
                    client.log_metric(run_id, key, float(value))
                batch = []
                with (Path(item['folder']) / 'equity.csv').open() as handle:
                    for step, row in enumerate(csv.DictReader(handle)):
                        timestamp = int(datetime.fromisoformat(row['date']).replace(tzinfo=timezone.utc).timestamp() * 1000)
                        batch.extend(Metric(key, float(row[key]), timestamp, step) for key in ('equity_usd', 'return_pct', 'drawdown_pct'))
                        if len(batch) >= 900:
                            client.log_batch(run_id, metrics=batch)
                            batch = []
                if batch:
                    client.log_batch(run_id, metrics=batch)
                client.log_artifacts(run_id, item['folder'], artifact_path='report')
                client.log_artifact(run_id, str(bundle_path), artifact_path='provenance')
                client.set_terminated(run_id, 'FINISHED')
            except Exception:
                client.set_terminated(run_id, 'FAILED')
                raise
        # Add the derived overall score once to previously imported runs as well.
        value = item['metrics']['calmar_full_period']
        existing = client.get_metric_history(run_id, 'calmar_full_period')
        if existing:
            if len(existing) != 1 or abs(existing[0].value - value) > 1e-12:
                raise ValueError('Existing Calmar differs from the report contract.')
        else:
            client.log_metric(run_id, 'calmar_full_period', value)
        client.log_param(run_id, 'strategy_rule', 'EMA50 > EMA200, long/cash' if item['mode'] == 'trend' else 'Buy once and hold; EMA parameters not used')
        client.log_artifacts(run_id, item['folder'], artifact_path='report')
        client.log_artifact(run_id, str(bundle_path), artifact_path='provenance')
        registry['runs'].append({'mode': item['mode'], 'run_id': run_id})
    (bundle_path.parent / 'mlflow-runs.json').write_text(json.dumps(registry, indent=2))
    print(json.dumps(registry))


if __name__ == '__main__':
    main()
