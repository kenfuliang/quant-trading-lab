---
name: trade-experiment
description: Execute an explicitly scoped, bounded offline trading experiment on saved inputs and reconcile its artifacts; distinguish completed simulations from valid independent research evidence.
---

# Execute a bounded offline experiment

Read [execution policy](../../../docs/research-development.md#experiment-execution)
and the requested frozen plan. Require its rule variants, trial/resource limits,
input identity, dates/splits, benchmark, costs/financing, metrics and stopping
conditions. Resolve missing decisions that alter the experiment before running;
do not fill them using whichever setting improves the observed score.

Inspect the current runner and saved inputs before choosing an entrypoint. The
bounded saved-SPY path is `scripts/bounded_study.py PLAN.json`: default is preflight;
`--execute` runs the exact supported plan. Follow the
[execution contract](../../../docs/research-development.md#experiment-execution),
including coordinator reservation of aggregate financial attempts/deadline before
launch; its per-plan case limit does not enforce a multi-study budget. Match the
actual schema/support in `research/bounded_study.py`; preserve prior failed outputs.

For the catalogue batch, the
existing `scripts/strategy_suite.py` has fixed strategy IDs, exposure targets,
source path and financial assumptions; it is not a generic arbitrary-plan runner.
Only use it when that exact batch is requested. From the repository root:

```sh
.venv/bin/python scripts/strategy_suite.py --skip-import --workers 3
```

`--skip-import` avoids the otherwise automatic MLflow import; it still renders
local report files. Worker count must be 1–4 and within the requested resource
budget. Do not use `make strategy-suite` for a strictly offline run: it also
starts local services, and the default runner imports to MLflow. Browser/service
start and MLflow writes need to fall within the user-requested scope. Do not
download inputs, install dependencies, connect to a broker or submit orders as
part of an offline run.

The current runner hashes its declared code/config/data identity, writes a
manifest and independent per-case Decimal reconciliation, and verifies artifact
hashes before reusing a completed directory. A cached reuse is not a fresh trial.
Its hash covers a declared file list, not the entire environment: record Git SHA,
relevant dirty-file hashes, dependency identity, command and exit separately.
Retain failed/incomplete directories; do not delete them to force a retry.

For a different plan, identify the missing runner capability and scope its
implementation through the development workflow; do not silently repurpose this
batch, widen the search or invent unsupported costs/instruments. Run relevant
offline checks after an implementation change.

Close with requested versus actual variants, new execution versus cache reuse,
status/exit, source and manifest paths/hashes, audit results, missing/failed cases
and comparison eligibility. Verify artifacts exist and agree with the manifest;
a dashboard rendering or process exit alone is insufficient. Preserve failures
and partial results, then stop or retry only within the plan's declared bounds.
Successful ledger reconciliation proves modeled accounting, not native execution
parity, untouched holdout status, predictive edge or paper/live readiness.
