"""Reaudit frozen local ETF snapshots; never downloads or executes strategies."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

import pandas as pd
from research.evaluation.etf_input_audit import audit_chart
from research.studies.spy.spy_backtest import load_data
from research.studies.checkpoint_20261031.multi_asset_plan import REQUIRED_GATES, require_ready
from research.evaluation.saved_review import verify_artifacts


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(output):
    parent = Path('.local/etf-readiness')
    old = json.loads((parent/'state.json').read_text())
    reports, frames, payloads = [], {}, {}
    for request in old['snapshot_requests']:
        if request['status'] != 'received':
            raise ValueError('Expected frozen three-asset inputs missing.')
        source = Path(request['path'])
        if sha(source) != request['sha256']:
            raise ValueError('Frozen ETF source changed.')
        payload = json.loads(source.read_text())
        receipt, frame = audit_chart(payload, request['symbol'])
        frames[request['symbol']], payloads[request['symbol']] = frame, payload
        receipt.update(source=str(source), sha256=sha(source),
                       evaluation_rows=len(frame.loc['2006-01-03':'2025-12-31']))
        reports.append(receipt)
    if set(frames) != {'SPY', 'IEF', 'GLD'}:
        raise ValueError('Exact three-asset universe required.')
    source = Path('reports/spy/20261024-235746-728801/source-data.json')
    spy, dividends, _ = load_data(source)
    spy.index = pd.to_datetime(spy.index)
    common = spy.index.intersection(frames['SPY'].index)
    if len(common) != 5305:
        raise ValueError('Expected SPY overlap changed.')
    columns = ['open', 'high', 'low', 'close']
    difference = spy.loc[common, columns].round(2) - frames['SPY'].loc[common, columns].round(2)
    events = payloads['SPY']['chart']['result'][0].get('events', {}).get('dividends', {})
    newdiv = {pd.Timestamp(e['date'], unit='s', tz='UTC').tz_convert('America/New_York').strftime('%Y-%m-%d'): e['amount']
              for e in events.values()}
    olddiv = {day: value for day, value in dividends.items()
              if common[0].strftime('%Y-%m-%d') <= day <= common[-1].strftime('%Y-%m-%d')}
    parity = dict(original_spy_sha256=sha(source), overlapping_rows=len(common),
                  rounded_ohlc_mismatching_cells=int((difference.abs() > 1e-9).sum().sum()),
                  maximum_rounded_ohlc_difference=float(difference.abs().max().max()),
                  distribution_date_sets_match=set(newdiv) == set(olddiv),
                  maximum_distribution_difference=max([abs(newdiv[k]-olddiv[k]) for k in newdiv if k in olddiv], default=0))
    native = Path('.local/multi-asset-unlock-v1/native-2')
    native_proof = json.loads((native/'proof.json').read_text())
    validation = json.loads(Path('.local/multi-asset-unlock-v1/validation.json').read_text())
    if validation['make_check_exit'] != 0 or validation['code_hashes'] != {
            name: sha(name) for name in ('research/multi_asset.py', 'research/multi_asset_plan.py', 'tests/test_multi_asset.py')}:
        raise ValueError('Current synthetic validation missing or stale.')
    def planner_ast(path):
        module = ast.parse(Path(path).read_text())
        return ast.dump(next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'plan_rebalance'))
    if planner_ast('research/multi_asset.py') != planner_ast(native/'source-research_multi_asset.py'):
        raise ValueError('Allocator changed since native seam proof.')
    gates = {name: False for name in REQUIRED_GATES}
    # These are available proofs, not a generic boolean override for absent data.
    gates['monthly_signals_synthetic_tests_passed'] = True
    gates['cash_allocator_native_synthetic_probe_passed'] = native_proof['status'] == 'synthetic_native_allocator_seam_passed'
    report = dict(status='not_ready', new_market_data_downloads=0, historical_financial_attempts=0,
                  inputs=reports, prior_input_manifest_verified=verify_artifacts(parent/'input-audit'),
                  native_manifest_verified=verify_artifacts(native),
                  common_observed_calendar_equal=all(frame.index.equals(frames['SPY'].index) for frame in frames.values()),
                  observed_intersection_is_not_calendar_qualification=True,
                  spy_snapshot_parity=parity, remaining_gates=gates,
                  synthetic_test_evidence=validation,
                  native_planner_ast_matches_current=True,
                  native_receivable_revision_note='Recorded probe source is preserved. A subsequent stricter payment-date input guard has unit coverage only; no further native run or corporate-action readiness claim.')
    try:
        require_ready(report)
    except ValueError as error:
        report['expected_launch_rejection'] = str(error)
    else:
        raise AssertionError('Do not declare historical eligibility without source qualifications.')
    output.mkdir(parents=True, exist_ok=False)
    (output/'readiness.json').write_text(json.dumps(report, indent=2)+'\n')
    (output/'manifest.json').write_text(json.dumps(dict(artifact_hashes={
        'readiness.json': sha(output/'readiness.json')}), indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.output), indent=2))
