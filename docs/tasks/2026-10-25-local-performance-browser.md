---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# Local native reports and MLflow

Work status: complete for the saved-SPY slice. User requested native Nautilus reports and local MLflow
browser comparison using existing SPY results. This is an explicitly requested M2
reporting slice; M1 catalog work remains planned.

Acceptance: generate two native HTML reports from saved curves/metrics without a
strategy rerun; preserve source hashes and original capital/assumptions; import
two distinguishable MLflow runs idempotently; verify browser reports and run
comparison; provide local start/stop commands and reconstruction instructions.
Use separate MLflow dependencies if needed to preserve the engine environment.
Bind browser servers to loopback and serve only generated report artifacts.

## Results and validation

Native HTML reports rendered for both portfolios; original input files were read,
not rewritten. Audited metrics and all daily equity/return/drawdown histories were
imported into two finished local MLflow runs. Source capital/period/cost/dividend
assumptions are visible in the browser. [Machine-readable receipt](evidence/2026-10-25-performance-browser.json)
records source snapshot identity, run IDs, metric reconciliation and history counts.

- `make check`: exit 0; eight tests passed, including new initial-loss/drawdown
  baseline and duplicate-date rejection checks; dependency and documentation checks pass.
- Both installed environments passed `pip check` (exit 0).
- Repeated starts/imports retained exactly two FINISHED runs and exactly 5,284
  points per daily metric (5,283 sessions plus explicit initial anchor); saved
  summary metrics match within 1e-8 and report artifacts are present.
- Stop removed both owned listeners; immediate restart and import completed.
  A restart port preflight issue found during development was corrected and retested.
- Browser verification: both native reports visibly inspected for audited values
  and chart sections; buy-and-hold ending value 629,586.54, CAGR 9.1607% and
  drawdown -51.6800% confirmed in the rendered view. Home links and direct MLflow
  comparison visibly verified; two strategy names and matching balances displayed.
- Browser screenshot retained at ignored `.local/screenshots/mlflow-comparison.png`.
- Core Nautilus remains 1.231.0; Plotly 6.9.0 added; MLflow 3.17.2 isolated under
  `.local/venvs/mlflow`. No outdated resolver fallback installed.

No strategy experiment, broker connection or order was run. Existing fixture tests
were rerun as regression checks. Fresh reconstruction of both environments and an
MLflow backup/restore exercise were not performed. Generic strategy import,
comparison eligibility and native-analyzer metric equivalence remain planned.
This does not complete all M2 gates or M1 catalog work.

## Ownership and operation

[Performance SOP](../operations/performance.md) owns start/stop/setup/storage;
[decision 0003](../decisions/0003-local-performance-browser.md) owns dependency and
storage rationale. Root status, matrix, architecture and roadmap were updated.
Servers are currently left running on loopback for the user. Git branch main still
has no baseline commit; no remote publication performed.

## Implementation fingerprints

- `reporting/saved_runs.py`: `bdeeda2b76757137b5a1a0961ea2f3fc5cc62cd9bd3dd9ac437957e7e472e21d`
- `scripts/performance.py`: `04bba3184cc30bd02793ac7e73d1744748c8abbc265136765f1b289043d78dae`
- `scripts/import_performance_mlflow.py`: `0cd730000ec64697df81887b7e9fb887bdc4d4517228a751ed9697482c7d7a9a`
- `requirements.lock.txt`: `f1ffe0e2cbfc09b02e6ab664b54fc2eaa1457f32338d90f0f70c26fcc4bcf5cc`
- `requirements-mlflow.lock.txt`: `f4c86d17c16e3f2c250f04a72befa58c6cae69cc11e8fb6a1b9abf73dc01045e`
