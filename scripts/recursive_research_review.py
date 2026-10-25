#!/usr/bin/env python3
"""Independently inspect saved SPY ledgers; never execute a financial simulation."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(values, annualize_days=None):
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Positive finite equity required for this review.')
    gain = values[-1] / values[0] - 1
    if annualize_days is not None:
        gain = (values[-1] / values[0]) ** (365.25 / annualize_days) - 1
    dd = float(np.min(values / np.maximum.accumulate(values) - 1))
    changes = values[1:] / values[:-1] - 1
    sd = changes.std(ddof=1) if len(changes) > 1 else 0
    sr = float(changes.mean() / sd * np.sqrt(252)) if sd > 1e-15 else None
    return {'return_pct': float(gain * 100), 'drawdown_pct': dd * 100,
            'calmar': float(gain / abs(dd)) if dd else None, 'sharpe': sr}


def inspect(folder, capital=300000):
    folder = Path(folder)
    curve = pd.read_csv(folder / 'ledger.csv', parse_dates=['date']).set_index('date')
    if curve.index.has_duplicates or not curve.index.is_monotonic_increasing:
        raise ValueError('Duplicated/unordered ledger dates.')
    eq = np.r_[capital, curve.equity_usd.to_numpy()]
    result = metrics(eq, (curve.index[-1] - curve.index[0]).days)
    result.update({key: float(curve[key].sum()) for key in
                   ('commission_usd', 'slippage_usd', 'financing_usd', 'dividend_usd')})
    actual = curve.shares * curve.close / curve.equity_usd
    result.update(sessions=len(curve), ending_equity_usd=float(eq[-1]),
                  mean_close_exposure=float(actual.mean()),
                  fraction_sessions_invested=float((curve.shares != 0).mean()),
                  trades=len(pd.read_csv(folder / 'trades.csv')))
    # Recovery of the deepest full-path close-equity drawdown, capital anchor included.
    dd = eq / np.maximum.accumulate(eq) - 1
    trough = int(dd.argmin()); peak = int(np.argmax(eq[:trough + 1]))
    recovered = np.flatnonzero(eq[trough:] >= eq[peak])
    recovery = int(trough + recovered[0]) if len(recovered) else None
    labels = ['initial-capital'] + curve.index.strftime('%Y-%m-%d').tolist()
    result['worst_drawdown_episode'] = {'peak': labels[peak], 'trough': labels[trough],
        'recovery': labels[recovery] if recovery is not None else None,
        'sessions_peak_to_recovery': recovery - peak if recovery is not None else None,
        'censored_at_end': recovery is None}
    previous = capital; annual = []
    for year, group in curve.groupby(curve.index.year):
        row = {'period': str(year), **metrics(np.r_[previous, group.equity_usd.to_numpy()])}
        annual.append(row); previous = float(group.equity_usd.iloc[-1])
    if (folder / 'scores.json').exists():
        saved = json.loads((folder / 'scores.json').read_text())
    else:
        saved = [json.loads((folder / 'metrics.json').read_text()), *pd.read_csv(folder / 'annual.csv').to_dict('records')]
    checks = []
    for actual_row, saved_row in zip([dict(period='Overall', **result), *annual], saved, strict=True):
        if str(actual_row['period']) != str(saved_row['period']):
            raise ValueError('Score period mismatch.')
        for key in ('return_pct', 'drawdown_pct', 'calmar', 'sharpe'):
            a, b = actual_row[key], saved_row[key]
            if a is None:
                passed = b is None or not np.isfinite(b)
                delta = None
            else:
                delta = abs(a - b); passed = delta <= 1e-9
            if not passed:
                raise ValueError(f'Independent metric mismatch {folder}/{actual_row["period"]}/{key}')
            checks.append({'period': str(actual_row['period']), 'metric': key, 'absolute_difference': delta})
    return {'overall': result, 'annual': annual, 'metric_checks': checks,
            'artifact_hashes': {p.name: digest(p) for p in sorted(folder.iterdir()) if p.is_file()}}


def verify_artifacts(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, sha in manifest['artifact_hashes'].items():
        if digest(directory / name) != sha:
            raise ValueError('Artifact hash mismatch: ' + name)
    return {'manifest_sha256': digest(directory / 'manifest.json'),
            'artifact_count': len(manifest['artifact_hashes'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--cases', nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'schema_version': 1, 'observation_kind': 'read_only_analysis',
              'input_directory': str(args.directory), **verify_artifacts(args.directory),
              'cases': {name: inspect(args.directory / name) for name in args.cases},
              'reviewer_code_sha256': digest(__file__), 'executed_financial_trials': 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError('Preserve existing receipt; select a new output path.')
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({name: data['overall'] for name, data in report['cases'].items()}, indent=2))


if __name__ == '__main__':
    main()
