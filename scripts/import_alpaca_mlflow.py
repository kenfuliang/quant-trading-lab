#!/usr/bin/env python3
"""Import redacted operational summaries only; run in isolated MLflow env."""
import hashlib
import json
from pathlib import Path
import sys
from mlflow import MlflowClient


def main():
    path = Path(sys.argv[1]).resolve()
    raw = path.read_bytes()
    result = json.loads(raw)
    fingerprint = hashlib.sha256(raw).hexdigest()
    client = MlflowClient(tracking_uri="http://127.0.0.1:5050")
    name = "Alpaca paper integration — operational evidence"
    experiment = client.get_experiment_by_name(name)
    exp_id = experiment.experiment_id if experiment else client.create_experiment(name)
    found = client.search_runs([exp_id], filter_string=f"tags.source_sha256 = '{fingerprint}'")
    finished = [r for r in found if r.info.status == "FINISHED"]
    if finished:
        run_id = finished[0].info.run_id
    else:
        run = client.create_run(exp_id, tags={"mlflow.runName": result["mode"] + " · " + result["status"],
            "source_sha256": fingerprint, "evidence_kind": result["evidence_kind"],
            "financial_performance_evidence": "false", "strategy": result["strategy"]})
        run_id = run.info.run_id
        try:
            for key in ["mode", "strategy", "status", "max_shares", "max_notional_usd", "max_orders", "sizing_change", "order_policy_change", "reconciliation_scope"]:
                client.log_param(run_id, key, str(result[key]))
            for key in ["native_fills", "broker_submissions", "broker_post_count", "submissions", "open_orders", "warmup_bars"]:
                if key in result:
                    client.log_metric(run_id, key, result[key])
            if "market_open" in result:
                client.log_metric(run_id, "market_open", int(result["market_open"]))
            client.log_artifact(run_id, str(path), artifact_path="redacted")
            client.set_terminated(run_id, "FAILED" if result["status"] in ["failed_preserved", "reconciliation_required"] else "FINISHED")
        except Exception:
            client.set_terminated(run_id, "FAILED")
            raise
    registry = {"experiment_id": exp_id, "run_id": run_id,
                "url": f"http://127.0.0.1:5050/#/experiments/{exp_id}/runs/{run_id}"}
    (path.parent / "mlflow.json").write_text(json.dumps(registry, indent=2) + "\n")
    print(json.dumps(registry))


if __name__ == "__main__":
    main()
