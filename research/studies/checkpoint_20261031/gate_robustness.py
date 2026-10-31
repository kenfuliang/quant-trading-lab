"""One new bounded epoch; frozen rules, explicit stale-signal stress, no sweeps."""
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

from research.studies.spy import risk_gate_study as old
from research.studies.spy.risk_gate_ablation import frames as frozen_frames
from research.evaluation.risk_gate_analysis import blocks
from reporting.risk_gate_review import verify_temporal_details
from research.evaluation.saved_review import verify_artifacts

PLAN = Path('research/plans/spy-gate-robustness-v1.json')
PROTOCOL = Path('docs/tasks/2026-10-25-rsi-gate-robustness.md')
PARENT = Path('.local/performance/risk-gate/20261025-epoch-v1')
RULES = ('gate_ema', 'ema', 'buy_hold_entry_only')
CONTEXTS = (('base', 5, 0), ('expensive', 25, 0), ('delayed', 25, 1))
CASES = [dict(id=f'{context}_{rule}', context=context, rule=rule, cost_bps=cost,
              signal_delay=delay if rule != 'buy_hold_entry_only' else 0)
         for context, cost, delay in CONTEXTS for rule in RULES]
CODE = tuple(dict.fromkeys((*old.CODE, 'research/risk_gate_ablation.py',
    'reporting/risk_gate_review.py', 'research/gate_robustness.py',
    'tests/test_gate_robustness.py')))
RANGES = [('2005-01-03', '2011-12-30'), ('2012-01-03', '2018-12-31'),
          ('2019-01-02', '2025-12-31')]


def delayed_frame(frame, delay):
    """Delay only decision fields on warmup-inclusive data, preserving price dates."""
    if delay not in (0, 1):
        raise ValueError('Only zero/one additional session supported.')
    result = frame.copy()
    if delay and 'rebalance_policy' in frame:
        raise ValueError('Standing entry-only control has no recurring signal.')
    if delay:
        for key in ('allocation_factor', 'base_target', 'intended_target'):
            result[key] = frame[key].shift(1).fillna(0.)
        result['want_long'] = frame.want_long.shift(1, fill_value=False)
    return result


def joint_claim(gate, control):
    eps = 1e-9
    changes = dict(cagr_pp=gate['return_pct'] - control['return_pct'],
                   drawdown_improvement_pp=gate['drawdown_pct'] - control['drawdown_pct'],
                   recovery_sessions_saved=control['duration'] - gate['duration'])
    no_worse = (changes['cagr_pp'] >= -eps and
                changes['drawdown_improvement_pp'] >= -eps and
                changes['recovery_sessions_saved'] >= 0)
    better = (changes['cagr_pp'] > eps or changes['drawdown_improvement_pp'] > eps or
              changes['recovery_sessions_saved'] > 0)
    return dict(passed=bool(no_worse and better), **changes)


def preflight(p):
    if (p['schema'] != 'spy-gate-robustness-v1' or p['cases'] != CASES or
            p['max_attempts'] != 9 or p['wall_seconds'] != 900 or
            p['financial_workers'] != 1 or p['automatic_retries'] != 0):
        raise ValueError('Frozen bounds/rules changed.')
    if p['model'] != asdict(old.FinancingModel()):
        raise ValueError('Financial model changed.')
    if p['code_hashes'] != {f: old.digest(f) for f in CODE}:
        raise ValueError('Executable identity changed.')
    if old.digest(PROTOCOL) != p['protocol_sha256']:
        raise ValueError('Protocol changed after freeze.')
    if old.digest(PARENT / 'manifest.json') != p['parent_manifest_sha256']:
        raise ValueError('Parent evidence identity changed.')
    verify_artifacts(PARENT)
    expected_source = json.loads(old.DESIGN.read_text())['source']
    if p['source'] != expected_source or old.digest(p['source']['path']) != p['source']['sha256']:
        raise ValueError('Source identity changed.')
    raw, dividends, _ = old.load_data(Path(p['source']['path']))
    raw = raw.round(2)
    raw.index = pd.to_datetime(raw.index)
    if len(raw) != 5535:
        raise ValueError('Warmup coverage changed.')
    data, _ = frozen_frames(raw)
    frames = {}
    for case in CASES:
        frame = delayed_frame(data[case['rule']], case['signal_delay'])
        frame = frame.loc['2005-01-03':'2025-12-31'].copy()
        frame.index = frame.index.strftime('%Y-%m-%d')
        if len(frame) != 5283 or frame.isna().any().any():
            raise ValueError('Incomplete evaluation coverage.')
        frames[case['id']] = frame
    return frames, dividends


def freeze():
    if PLAN.exists():
        raise ValueError('No replacement or refreeze.')
    p = dict(schema='spy-gate-robustness-v1', created_utc=datetime.now(timezone.utc).isoformat(),
             protocol_sha256=old.digest(PROTOCOL), code_hashes={f: old.digest(f) for f in CODE},
             source=json.loads(old.DESIGN.read_text())['source'], model=asdict(old.FinancingModel()),
             cases=CASES, max_attempts=9, wall_seconds=900, financial_workers=1, automatic_retries=0,
             parent_manifest_sha256=old.digest(PARENT / 'manifest.json'),
             git_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
             git_status=subprocess.check_output(['git', 'status', '--short'], text=True))
    preflight(p)
    # Exclusive creation rather than an overwrite-capable writer.
    with PLAN.open('x') as stream:
        json.dump(p, stream, indent=2, allow_nan=False)
        stream.write('\n')


def run_case(p, index, out):
    frames, dividends = preflight(p)
    case = CASES[index]
    state = json.loads((out / 'state.json').read_text())
    if state['plan_sha256'] != old.digest(PLAN) or state['attempts'][index]['status'] != 'running':
        raise ValueError('No active reservation.')
    folder = out / case['id']
    folder.mkdir()
    model = old.FinancingModel(**(p['model'] | dict(cost_bps=case['cost_bps'])))
    mode = 'buy_hold' if case['rule'] == 'buy_hold_entry_only' else 'trend'
    frame = frames[case['id']]
    curve, trades = old.simulate(frame, dividends, mode, 1, model)
    frame.to_csv(folder / 'signal.csv')
    curve.to_csv(folder / 'ledger.csv')
    trades.to_csv(folder / 'trades.csv', index=False)
    old.validate_financial_outputs(frame, curve, trades)
    old.write(folder / 'audit.json', old.reconcile(frame, dividends, curve, trades, mode, 1, model))
    old.write(folder / 'scores.json', old.score_rows(curve, model, case['id'], mode, 1))
    review = old.inspect(folder)
    old.write(folder / 'independent-metrics.json', review)
    eq = pd.Series(np.r_[model.capital, curve.equity_usd],
                   index=pd.to_datetime(['2004-12-31', *curve.index]))
    temporal, table = old.analyze_temporal(eq, initial_capital=model.capital)
    audit = old.independent_temporal(eq, temporal, table)
    audit['details'] = verify_temporal_details(eq, temporal)
    old.write(folder / 'temporal.json', temporal)
    old.write(folder / 'temporal-audit.json', audit)
    table.to_csv(folder / 'temporal.csv', index_label='date')
    old.write(folder / 'blocks.json', blocks(curve, model.capital, RANGES))
    return dict(id=case['id'], metric_checks=len(review['metric_checks']), audited=True)


def review(out):
    rows, annual, block_rows = [], [], []
    for case in CASES:
        folder = out / case['id']
        scores = json.loads((folder / 'scores.json').read_text())
        temporal = json.loads((folder / 'temporal.json').read_text())
        row = dict(scores[0], context=case['context'], rule=case['rule'],
                   duration=temporal['longest_underwater_duration_sessions'],
                   right_censored=temporal['longest_underwater_right_censored'],
                   worst_21_return_pct=100 * temporal['worst_returns']['21']['return'],
                   daily_es95_pct=100 * temporal['historical_daily_es95']['tail_mean_return'])
        rows.append(row)
        annual.extend(dict(item, context=case['context'], rule=case['rule']) for item in scores[1:])
        block_rows.extend(dict(item, context=case['context'], rule=case['rule'])
                          for item in json.loads((folder / 'blocks.json').read_text()))
    comparisons = {}
    parent = pd.read_csv(PARENT / 'overall.csv').set_index('id')
    parity = []
    for row in rows:
        if row['context'] != 'base':
            continue
        name = '5_ablate_ema' if row['rule'] == 'gate_ema' else '5_' + row['rule']
        for current, saved in (('return_pct', 'cagr_pct'), ('drawdown_pct', 'drawdown_pct'),
                               ('sharpe', 'sharpe'), ('calmar', 'calmar'),
                               ('duration', 'longest_underwater_sessions')):
            delta = abs(row[current] - float(parent.loc[name, saved]))
            if delta > (0 if current == 'duration' else 1e-9):
                raise ValueError('Frozen baseline parity failed: ' + name + '/' + current)
            parity.append(dict(id=name, metric=current, absolute_difference=delta))
    for context, _, _ in CONTEXTS:
        pair = {row['rule']: row for row in rows if row['context'] == context}
        comparisons[context] = joint_claim(pair['gate_ema'], pair['ema'])
    for name in ('ledger.csv', 'trades.csv', 'scores.json', 'signal.csv'):
        # scores embed case IDs, unlike the actual account and signals.
        if name == 'scores.json':
            continue
        if old.digest(out / 'expensive_buy_hold_entry_only' / name) != old.digest(out / 'delayed_buy_hold_entry_only' / name):
            raise ValueError('Standing buy/hold control changed in stale-signal context.')
    pd.DataFrame(rows).to_csv(out / 'overall.csv', index=False)
    pd.DataFrame(annual).to_csv(out / 'annual.csv', index=False)
    pd.DataFrame(block_rows).to_csv(out / 'blocks.csv', index=False)
    decision = dict(joint_claim='retain_for_independent_validation' if all(c['passed'] for c in comparisons.values())
                    else 'reject_joint_execution_robustness_claim', comparisons=comparisons,
                    historical_scope='previously viewed development history; no alpha or promotion proof',
                    duplicate_buy_hold_control_verified=True, baseline_parity_checks=parity)
    old.write(out / 'decision.json', decision)
    return decision


def execute(p):
    preflight(p)
    out = Path('.local/gate-robustness') / old.digest(PLAN)[:16]
    out.mkdir(parents=True, exist_ok=False)  # consumed output identity cannot be reused
    old.write(out / 'plan.json', p)
    state = dict(status='running', plan_sha256=old.digest(PLAN), actual_attempts=0,
                 started_utc=datetime.now(timezone.utc).isoformat(),
                 attempts=[dict(id=c['id'], status='reserved') for c in CASES])
    old.write(out / 'state.json', state)
    start = time.monotonic()
    try:
        for i, case in enumerate(CASES):
            remaining = p['wall_seconds'] - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError('Aggregate financial wall limit.')
            state['attempts'][i]['status'] = 'running'
            state['actual_attempts'] += 1
            old.write(out / 'state.json', state)
            child = subprocess.run([sys.executable, '-m', 'research.gate_robustness', '--case', str(i),
                                    '--output', str(out)], capture_output=True, text=True, timeout=remaining)
            (out / (case['id'] + '.log')).write_text(child.stdout + child.stderr)
            if child.returncode:
                raise RuntimeError(f'{case["id"]}: exit {child.returncode}; preserve failure, no retry.')
            state['attempts'][i]['status'] = 'completed'
            old.write(out / 'state.json', state)
        decision = review(out)
        state.update(status='completed', decision=decision['joint_claim'])
    except Exception as error:
        for attempt in state['attempts']:
            if attempt['status'] == 'running':
                attempt.update(status='failed', error=str(error))
        state.update(status='stopped_inconclusive_no_retry', error=str(error))
        raise
    finally:
        state['elapsed_seconds'] = time.monotonic() - start
        old.write(out / 'state.json', state)
        old.write(out / 'manifest.json', dict(status=state['status'], plan_sha256=old.digest(PLAN),
            artifact_hashes={str(f.relative_to(out)): old.digest(f) for f in sorted(out.rglob('*')) if f.is_file()}))
        print(str(out))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--case', type=int, choices=range(9))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.freeze:
        freeze()
        return
    p = json.loads(PLAN.read_text())
    if args.case is not None:
        print(json.dumps(run_case(p, args.case, args.output), allow_nan=False))
    elif args.execute:
        execute(p)
    else:
        preflight(p)
        print('Preflight passed; no financial attempt.')


if __name__ == '__main__':
    main()
