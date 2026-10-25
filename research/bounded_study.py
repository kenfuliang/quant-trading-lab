"""Immutable, bounded offline studies using the existing audited SPY ledger.

No downloads, service discovery, MLflow writes or broker clients are invoked.
The caller owns global attempt reservation; max_cases is only a per-plan bound.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

from research.spy_backtest import load_data
from research.daily_signals import build_signal, DEFINITIONS as DAILY
from research.allocation_overlays import build_allocation_signal, DEFINITIONS as ALLOCATION
from research.model_signals import build_model_signal, DEFINITIONS as MODELS
from research.overnight_signal import build_overnight_signal, DEFINITIONS as OVERNIGHT
from research.leveraged_spy import FinancingModel, simulate, score_rows
from research.leverage_audit import reconcile

ROOT = Path(__file__).resolve().parents[1]
CODE_FILES = (
    'research/bounded_study.py', 'scripts/bounded_study.py', 'research/spy_backtest.py',
    'requirements.txt', 'requirements.lock.txt',
    'research/daily_signals.py', 'research/allocation_overlays.py',
    'research/model_signals.py', 'research/overnight_signal.py',
    'research/leveraged_spy.py', 'research/leverage_audit.py',
    'reporting/annual.py', 'research/leverage-model.md',
    'research/daily-strategies.md', 'research/allocation-strategies.md',
    'research/model-strategies.md', 'research/overnight-strategy.md',
)
SUPPORTED = DAILY | ALLOCATION | MODELS | OVERNIGHT
NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _json_scores(value):
    """Represent undefined financial ratios as null, preserving native JSON types."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_scores(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_scores(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError('Unsupported financial score value: ' + type(value).__name__)


def current_code_hashes():
    return {name: digest(ROOT / name) for name in CODE_FILES}


def validate_plan(plan):
    """Validate declared policy before loading market data or creating output."""
    p = json.loads(canonical(plan))
    required = {'schema_version', 'plan_id', 'parent', 'hypothesis', 'assumptions',
                'evaluation', 'source', 'code_hashes', 'financing_model', 'max_cases', 'cases'}
    if set(p) != required or p['schema_version'] != 1:
        raise ValueError('Expected exact bounded-study schema version 1.')
    if not isinstance(p['plan_id'], str) or not NAME.fullmatch(p['plan_id']):
        raise ValueError('Invalid plan_id.')
    if any(not isinstance(p[n], str) or not p[n].strip() for n in ('parent', 'hypothesis')):
        raise ValueError('Parent and hypothesis must be declared.')
    if not isinstance(p['assumptions'], list) or not p['assumptions'] or any(not isinstance(x, str) or not x.strip() for x in p['assumptions']):
        raise ValueError('Explicit assumptions are required.')
    e = p['evaluation']
    if set(e) != {'label', 'start', 'end', 'expected_sessions'} or e['label'] != 'development/viewed-history':
        raise ValueError('Only explicitly viewed development history is supported.')
    if any(not isinstance(e[x], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', e[x]) for x in ('start', 'end')):
        raise ValueError('Evaluation dates must use YYYY-MM-DD.')
    if pd.Timestamp(e['start']) > pd.Timestamp(e['end']) or type(e['expected_sessions']) is not int or e['expected_sessions'] < 2:
        raise ValueError('Invalid evaluation coverage.')
    if type(p['max_cases']) is not int or not 1 <= p['max_cases'] <= 12:
        raise ValueError('Per-plan case budget must be between 1 and 12.')
    if not isinstance(p['cases'], list) or not 1 <= len(p['cases']) <= p['max_cases']:
        raise ValueError('Case count exceeds declared budget or is empty.')
    if set(p['financing_model']) != set(asdict(FinancingModel())):
        raise ValueError('Declare every financing parameter explicitly.')
    if any(type(x) not in (float, int) for x in p['financing_model'].values()):
        raise ValueError('Financing parameters must be numbers.')
    FinancingModel(**p['financing_model'])
    if set(p['source']) != {'path', 'sha256'} or not isinstance(p['source']['path'], str):
        raise ValueError('Expected explicit local source path and SHA256.')
    if not re.fullmatch(r'[0-9a-f]{64}', p['source']['sha256']):
        raise ValueError('Invalid source SHA256.')
    if set(p['code_hashes']) != set(CODE_FILES):
        raise ValueError('Declare all runner/financial code and method hashes.')
    names = set()
    for c in p['cases']:
        if not isinstance(c, dict) or set(c) not in ({'case_id', 'strategy_id', 'exposure'}, {'case_id', 'components', 'exposure'}):
            raise ValueError('Unsupported case fields or instrument.')
        if not isinstance(c['case_id'], str) or not NAME.fullmatch(c['case_id']) or c['case_id'] in names:
            raise ValueError('Case IDs must be unique safe names.')
        names.add(c['case_id'])
        if type(c['exposure']) not in (float, int) or c['exposure'] != 1:
            raise ValueError('Initial bounded pilot supports only 1x nominal exposure.')
        if 'strategy_id' in c:
            if type(c['strategy_id']) is not int or c['strategy_id'] not in SUPPORTED:
                raise ValueError('Unsupported saved-SPY adaptation.')
        else:
            parts = c['components']
            if not isinstance(parts, list) or not 1 <= len(parts) <= 12:
                raise ValueError('Expected 1-12 long/cash mixture components.')
            ids = set()
            for part in parts:
                if set(part) != {'strategy_id', 'weight'} or type(part['strategy_id']) is not int or part['strategy_id'] not in DAILY:
                    raise ValueError('Mixtures support existing daily long/cash direction rules only.')
                if part['strategy_id'] in ids:
                    raise ValueError('Duplicate mixture component.')
                ids.add(part['strategy_id'])
                if type(part['weight']) not in (float, int) or not math.isfinite(part['weight']) or not 0 <= part['weight'] <= 1:
                    raise ValueError('Mixture weights must be finite and nonnegative.')
            if not 0 < sum(x['weight'] for x in parts) <= 1:
                raise ValueError('Mixture weights must sum to a positive value at most one.')
    return p


def _verify_inputs(plan):
    source = Path(plan['source']['path'])
    if not source.is_absolute():
        source = ROOT / source
    if not source.is_file() or digest(source) != plan['source']['sha256']:
        raise ValueError('Source input hash mismatch.')
    if current_code_hashes() != plan['code_hashes']:
        raise ValueError('Code/method input hash mismatch.')
    return source


def preflight(plan):
    """Verify identity and coverage offline; do not create an attempt directory."""
    p = validate_plan(plan)
    source = _verify_inputs(p)
    raw, dividends, metadata = load_data(source)
    if metadata['sha256'] != p['source']['sha256']:
        raise ValueError('Loaded source hash mismatch.')
    raw = raw.round(2)
    raw.index = pd.to_datetime(raw.index)
    selected = raw.loc[p['evaluation']['start']:p['evaluation']['end']]
    if len(selected) != p['evaluation']['expected_sessions']:
        raise ValueError('Evaluation session count mismatch.')
    if selected.empty or pd.Timestamp(p['evaluation']['start']) < raw.index.min() or pd.Timestamp(p['evaluation']['end']) > raw.index.max():
        raise ValueError('Evaluation outside available source coverage.')
    return p, raw, dividends


def build_case_frame(raw, case):
    """Preserve builders' existing one-session lag; mixtures never shift again."""
    def build(identifier):
        builder = (build_signal if identifier in DAILY else build_allocation_signal
                   if identifier in ALLOCATION else build_model_signal
                   if identifier in MODELS else build_overnight_signal)
        result = builder(raw.copy(), identifier)
        if not result.index.equals(raw.index) or result.want_long.isna().any():
            raise ValueError('Invalid signal coverage or unknown direction.')
        return result
    if 'strategy_id' in case:
        return build(case['strategy_id'])
    result = raw[['open', 'low', 'close']].copy()
    result['allocation_factor'] = 0.0
    for part in case['components']:
        component = build(part['strategy_id'])
        result['allocation_factor'] += part['weight'] * component.want_long.astype(float)
    result['want_long'] = result.allocation_factor > 0
    return result


def validate_financial_outputs(frame, curve, trades):
    """Reject unaudited coverage/nonfinite account data before legacy replay/scoring.

    This complements direct Decimal accounting guards with stricter full-ledger
    numeric types, finite risk diagnostics and integer/boolean policy fields.
    """
    if not isinstance(curve, pd.DataFrame) or not isinstance(trades, pd.DataFrame):
        raise ValueError('Financial outputs must be data frames.')
    if curve.empty or not curve.index.equals(frame.index) or curve.index.has_duplicates:
        raise ValueError('Financial ledger coverage differs from the declared signal sessions.')
    required = {'cash', 'shares', 'close', 'equity_usd', 'effective_target_leverage',
                'financing_usd', 'dividend_usd', 'commission_usd', 'slippage_usd',
                'max_checked_leverage', 'min_margin_buffer_pct', 'forced_liquidations',
                'initial_margin_rejections', 'halted', 'insolvent'}
    if not required <= set(curve.columns):
        raise ValueError('Financial ledger is missing required account fields.')
    numeric = required - {'halted', 'insolvent'}
    for name in numeric:
        if not pd.api.types.is_numeric_dtype(curve[name]) or pd.api.types.is_bool_dtype(curve[name]) or not np.isfinite(curve[name].to_numpy(dtype=float)).all():
            raise ValueError('Nonfinite or nonnumeric financial ledger field: ' + name)
    for name in ('halted', 'insolvent'):
        if not pd.api.types.is_bool_dtype(curve[name]) or curve[name].isna().any():
            raise ValueError('Financial state flags must be explicit booleans.')
    for name in ('shares', 'forced_liquidations', 'initial_margin_rejections'):
        if (curve[name] < 0).any() or (curve[name] % 1 != 0).any():
            raise ValueError('Financial quantities/counts must be nonnegative integers.')
    if not trades.empty:
        columns = {'date', 'delta', 'fill_price', 'mark', 'reason', 'cash_after', 'shares_after'}
        if not columns <= set(trades.columns):
            raise ValueError('Financial trades missing required fields.')
        if trades['date'].isna().any() or not trades['date'].isin(frame.index).all():
            raise ValueError('Trade date lies outside declared signal sessions.')
        for name in columns - {'date', 'reason'}:
            if not pd.api.types.is_numeric_dtype(trades[name]) or pd.api.types.is_bool_dtype(trades[name]) or not np.isfinite(trades[name].to_numpy(dtype=float)).all():
                raise ValueError('Nonfinite or nonnumeric financial trade field: ' + name)
        if (trades[['fill_price', 'mark']] <= 0).any().any():
            raise ValueError('Financial trade prices must be positive.')
        if (trades['delta'] % 1 != 0).any() or (trades['delta'] == 0).any() or (trades['shares_after'] < 0).any() or (trades['shares_after'] % 1 != 0).any():
            raise ValueError('Financial trades require nonzero integer changes and nonnegative integer holdings.')
        if not trades['reason'].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError('Financial trade reasons must be explicit.')


def _read_trades(path):
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_manifest(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def run_plan(plan, output_root):
    """Run sequentially; preserve failures and verify completed caches before reuse."""
    p, raw, dividends = preflight(plan)
    fingerprint = hashlib.sha256(canonical(p).encode()).hexdigest()
    directory = Path(output_root) / fingerprint
    manifest_path = directory / 'manifest.json'
    if directory.exists():
        if not manifest_path.is_file():
            raise ValueError('Incomplete attempt directory retained.')
        saved = json.loads(manifest_path.read_text())
        if saved.get('status') != 'completed' or saved.get('fingerprint') != fingerprint or saved.get('plan') != p:
            raise ValueError('Failed/incomplete or incompatible attempt retained; new declared attempt required.')
        artifacts = saved.get('artifact_hashes', {})
        expected = {'plan.json', 'scores.csv'} | {f"{c['case_id']}/{name}" for c in p['cases'] for name in ('signal.csv', 'ledger.csv', 'trades.csv', 'scores.json', 'audit.json')}
        if set(artifacts) != expected or {c['case_id'] for c in saved.get('cases', [])} != {c['case_id'] for c in p['cases']}:
            raise ValueError('Completed cache missing required case/artifact evidence.')
        for name, sha in artifacts.items():
            if not (directory / name).is_file() or digest(directory / name) != sha:
                raise ValueError('Completed cache artifact hash mismatch: ' + name)
        expected_index = raw.loc[p['evaluation']['start']:p['evaluation']['end']].index.strftime('%Y-%m-%d')
        for c in p['cases']:
            folder = directory / c['case_id']
            signal = pd.read_csv(folder / 'signal.csv', index_col='date')
            if not signal.index.equals(expected_index):
                raise ValueError('Cached signal session coverage differs from plan.')
            curve = pd.read_csv(folder / 'ledger.csv', index_col='date')
            trades = _read_trades(folder / 'trades.csv')
            validate_financial_outputs(signal, curve, trades)
            audit = json.loads((folder / 'audit.json').read_text())
            difference = audit.get('maximum_difference_usd')
            if (audit.get('passed') is not True or audit.get('sessions') != len(curve)
                    or audit.get('fills') != len(trades) or type(difference) not in (int, float)
                    or not math.isfinite(difference) or not 0 <= difference <= .01):
                raise ValueError('Cached financial audit failed or coverage is inconsistent.')
        _verify_inputs(p)
        return {'directory': str(directory), 'status': 'completed', 'reused': True, 'manifest': saved}
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version': 1, 'fingerprint': fingerprint, 'plan': p, 'status': 'running',
                'created_utc': datetime.now(timezone.utc).isoformat(), 'cases': []}
    _write_manifest(manifest_path, manifest)
    (directory / 'plan.json').write_text(json.dumps(p, indent=2) + '\n')
    try:
        scores = []
        model = FinancingModel(**p['financing_model'])
        for case in p['cases']:
            _verify_inputs(p)
            folder = directory / case['case_id']
            folder.mkdir()
            frame = build_case_frame(raw, case).loc[p['evaluation']['start']:p['evaluation']['end']].copy()
            frame.index = frame.index.strftime('%Y-%m-%d')
            frame.to_csv(folder / 'signal.csv', index_label='date')
            curve, trades = simulate(frame, dividends, 'trend', case['exposure'], model)
            validate_financial_outputs(frame, curve, trades)
            audit = reconcile(frame, dividends, curve, trades, 'trend', case['exposure'], model)
            if audit.get('passed') is not True:
                raise ValueError('Financial audit did not pass.')
            _verify_inputs(p)
            rows = score_rows(curve, model, case['case_id'], 'trend', case['exposure'])
            for row in rows:
                row['case_id'] = case['case_id']
            curve.to_csv(folder / 'ledger.csv', index_label='date')
            trades.to_csv(folder / 'trades.csv', index=False)
            (folder / 'scores.json').write_text(json.dumps(_json_scores(rows), indent=2, allow_nan=False) + '\n')
            (folder / 'audit.json').write_text(json.dumps(audit, indent=2, allow_nan=False) + '\n')
            scores.extend(rows)
            manifest['cases'].append({'case_id': case['case_id'], 'audit': audit, 'sessions': len(curve)})
            _write_manifest(manifest_path, manifest)
        pd.DataFrame(scores).to_csv(directory / 'scores.csv', index=False)
        _verify_inputs(p)
        manifest['artifact_hashes'] = {str(q.relative_to(directory)): digest(q) for q in sorted(directory.rglob('*')) if q.is_file() and q != manifest_path}
        manifest['status'] = 'completed'
        manifest['completed_utc'] = datetime.now(timezone.utc).isoformat()
        _write_manifest(manifest_path, manifest)
    except Exception as error:
        manifest['status'] = 'failed'
        manifest['artifact_hashes'] = {str(q.relative_to(directory)): digest(q) for q in sorted(directory.rglob('*')) if q.is_file() and q != manifest_path}
        manifest['failure'] = {'type': type(error).__name__, 'message': str(error)}
        _write_manifest(manifest_path, manifest)
        raise
    return {'directory': str(directory), 'status': 'completed', 'reused': False, 'manifest': manifest}
