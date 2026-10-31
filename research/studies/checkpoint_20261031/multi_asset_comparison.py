"""Matched native comparison; historical launch requires a qualified input bundle.

This coordinator never downloads data or substitutes an unqualified local file.
The bundle is a reviewed evidence artifact, not a command-line waiver.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from research.studies.checkpoint_20261031.multi_asset import SYMBOLS, forward_total_return, monthly_decisions
from research.studies.checkpoint_20261031.multi_asset_plan import CASES
from research.studies.checkpoint_20261031.native_multi_asset import run_native
from research.studies.checkpoint_20261031.multi_asset_cash_audit import reconcile
from research.studies.spy.risk_gate_ablation import frames as gate_frames
from research.studies.spy.risk_gate_study import CODE as OLD_CODE, write
from research.studies.checkpoint_20261031.us_etf_calendar import sessions
from reporting.annual import sharpe, calmar
from reporting.temporal import analyze_temporal
from research.evaluation.risk_gate_analysis import independent_temporal
from reporting.risk_gate_review import verify_temporal_details
from research.evaluation.saved_review import metrics

ROOT = Path('.local/multi-asset-qualification-v2')
STATE = ROOT/'state.json'
BUNDLE = ROOT/'qualified-input-bundle.json'
PLAN = ROOT/'comparison-plan.json'
CODE = tuple(dict.fromkeys((*OLD_CODE, 'research/multi_asset.py','research/multi_asset_plan.py',
    'research/native_multi_asset.py','research/multi_asset_cash_audit.py','research/multi_asset_comparison.py',
    'research/risk_gate_ablation.py','research/us_etf_calendar.py','reporting/risk_gate_review.py',
    'research/etf_readiness_probe.py','research/issuer_actions.py','tests/test_multi_asset_qualification.py')))
GATES = ('price_use_permission','raw_price_semantics','actions_reconciled','payment_dates_complete',
         'calendar_coverage','availability_scope_disclosed','no_unhandled_splits','native_accounting_verified')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_bundle():
    if not BUNDLE.exists():
        raise ValueError('Qualified price-use/input bundle missing; historical launch blocked.')
    bundle = json.loads(BUNDLE.read_text())
    if bundle.get('schema') != 'qualified-three-etf-inputs-v1' or set(bundle.get('gates',{})) != set(GATES):
        raise ValueError('Incomplete input qualification schema.')
    missing = [name for name in GATES if bundle['gates'][name] is not True]
    if missing:
        raise ValueError('Historical launch blocked: '+', '.join(missing))
    required = ('prices','actions','calendar','permission_evidence','qualification_receipt')
    if set(bundle['files']) != set(required):
        raise ValueError('Exact price/action/calendar/permission/qualification evidence required.')
    for item in bundle['files'].values():
        if digest(item['path']) != item['sha256']:
            raise ValueError('Qualified source identity changed.')
    raw = pd.read_csv(bundle['files']['prices']['path'], parse_dates=['date'])
    if set(raw.symbol) != set(SYMBOLS) or raw.duplicated(['symbol','date']).any():
        raise ValueError('Exact three-asset identity/unique sessions required.')
    frames = {}
    for symbol, group in raw.groupby('symbol'):
        frame = group.set_index('date')[['open','high','low','close','volume']].sort_index()
        if not np.isfinite(frame.to_numpy(float)).all() or (frame[['open','high','low','close']] <= 0).any().any():
            raise ValueError('Invalid qualified prices.')
        expected = sessions(frame.index[0],frame.index[-1])
        if not frame.index.equals(expected) or frame.index[-1] != pd.Timestamp('2025-12-31'):
            raise ValueError('Qualified calendar coverage mismatch.')
        if (frame.high < frame[['open','close','low']].max(axis=1)).any() or (frame.low > frame[['open','close','high']].min(axis=1)).any():
            raise ValueError('Qualified OHLC envelope failure.')
        frames[symbol] = frame.round(2)
    if frames['SPY'].index[0] != pd.Timestamp('2004-01-02'):
        raise ValueError('Frozen gate requires original2004SPY warmup.')
    calendar = pd.read_csv(bundle['files']['calendar']['path'], parse_dates=['date'])
    if not pd.DatetimeIndex(calendar.date).equals(sessions('2004-01-02','2025-12-31')):
        raise ValueError('Saved independent calendar differs from qualified rules.')
    actions = json.loads(Path(bundle['files']['actions']['path']).read_text())
    if bundle.get('splits'):
        raise ValueError('Unhandled split; do not launch.')
    return bundle, frames, actions


def build_targets(raw, actions):
    common = sessions('2004-12-01','2025-12-31')
    indexes = {}
    for symbol in SYMBOLS:
        close = raw[symbol].loc[common,'close']
        distributions = pd.Series(0.,index=common)
        for action in actions:
            if action['symbol'] == symbol and pd.Timestamp(action['ex_date']) in common:
                distributions.loc[action['ex_date']] += float(action['amount'])
        # Index is anchored at the first *closing* mark, after that day's action.
        # No pre-anchor return is asserted. Original actions remain in their file.
        distributions.iloc[0] = 0.
        indexes[symbol] = forward_total_return(close,distributions,pd.Series(1.,index=common))
    decisions = monthly_decisions(pd.DataFrame(indexes),common)
    selected = sessions('2006-01-03','2025-12-31')
    dates = selected.strftime('%Y-%m-%d')
    targets = {name:{} for name in ('spy_entry_only','frozen_spy_gate','static_equal','trend_equal','relative_strength')}
    targets['spy_entry_only'][dates[0]] = dict(SPY=1,IEF=0,GLD=0)
    for event in decisions:
        day = event['execution_open']
        if day in dates:
            for name in ('static_equal','trend_equal','relative_strength'):
                targets[name][day] = event[name]
    gate, _ = gate_frames(raw['SPY'])
    for day, value in gate['gate_ema'].loc[selected,'intended_target'].items():
        targets['frozen_spy_gate'][day.strftime('%Y-%m-%d')] = dict(SPY=float(value),IEF=0,GLD=0)
    frames = {symbol: raw[symbol].loc[selected].copy() for symbol in SYMBOLS}
    for frame in frames.values():
        frame.index = frame.index.strftime('%Y-%m-%d')
    return frames, targets


def score(curve, name):
    equity = curve.equity_usd
    def row(period, values, days=None):
        returns = np.diff(values)/values[:-1]
        gain = values[-1]/values[0]-1
        if days is not None:
            gain = (values[-1]/values[0])**(365.25/days)-1
        drawdown = float((values/np.maximum.accumulate(values)-1).min()*100)
        result = dict(period=period, strategy=name, return_pct=float(gain*100), drawdown_pct=drawdown,
                      sharpe=sharpe(returns), calmar=calmar(float(gain*100),drawdown))
        reference = metrics(values,days)
        for key in ('return_pct','drawdown_pct','sharpe','calmar'):
            a,b = result[key],reference[key]
            if b is None:
                if a is not None and np.isfinite(a):
                    raise AssertionError('Undefined metric mismatch.')
            elif abs(a-b) > 1e-9:
                raise AssertionError('Independent metric mismatch: '+key)
        return result
    rows = [row('Overall',np.r_[300000,equity],(pd.Timestamp(curve.index[-1])-pd.Timestamp(curve.index[0])).days)]
    previous = 300000
    for year, group in equity.groupby(pd.to_datetime(equity.index).year):
        rows.append(row(str(year),np.r_[previous,group.to_numpy()]))
        previous = group.iloc[-1]
    return rows


def freeze():
    load_bundle()
    p = dict(schema='native-multi-asset-comparison-v1',bundle_sha256=digest(BUNDLE),cases=CASES,
             max_cases=10,financial_workers=1,wall_seconds=900,automatic_retries=0,
             code_hashes={name:digest(name) for name in CODE},
             methodology='docs/tasks/2026-10-25-multi-asset-qualification-v2.md',
             protocol_sha256=digest('docs/tasks/2026-10-25-multi-asset-qualification-v2.md'),
             account_policy='USD300000;99%pretrade investable budget excluding receivables;whole shares;no borrow;zero cash yield;USD1/order;per-action half-even-cent pay credits;raw close plus unpaid receivables NAV',
             observation_class='Previously viewed/restated development inputs; no independent alpha proof')
    with PLAN.open('x') as stream:
        json.dump(p,stream,indent=2)
        stream.write('\n')


def preflight():
    p = json.loads(PLAN.read_text())
    if (p['cases'] != CASES or p['max_cases'] != 10 or p['wall_seconds'] != 900 or
            p['financial_workers'] != 1 or p['automatic_retries'] != 0 or
            p['bundle_sha256'] != digest(BUNDLE) or p['code_hashes'] != {f:digest(f) for f in CODE} or
            p['protocol_sha256'] != digest(p['methodology'])):
        raise ValueError('Frozen comparison identity/bounds changed.')
    return p, load_bundle()


def case(index, out):
    p, (_,raw,actions) = preflight()
    state = json.loads(STATE.read_text())
    if (state['financial_attempts'][index]['status'] != 'running' or
            state['comparison_plan_sha256'] != digest(PLAN) or state.get('comparison_output') != str(out)):
        raise ValueError('Missing active financial reservation.')
    item = CASES[index]
    folder = out/item['id']
    folder.mkdir()
    frames,targets = build_targets(raw,actions)
    curve,trades,events = run_native(frames,targets[item['rule']],actions,cost_bps=item['cost_bps'])
    curve.to_csv(folder/'ledger.csv')
    trades.to_csv(folder/'trades.csv',index=False)
    write(folder/'events.json',events)
    audit = reconcile(frames,targets[item['rule']],actions,curve,trades,events,cost_bps=item['cost_bps'])
    write(folder/'audit.json',audit)
    write(folder/'scores.json',score(curve,item['id']))
    eq = pd.Series(np.r_[300000,curve.equity_usd],index=pd.to_datetime(['2005-12-30',*curve.index]))
    summary,table = analyze_temporal(eq,initial_capital=300000)
    ta = independent_temporal(eq,summary,table)
    ta['details'] = verify_temporal_details(eq,summary)
    write(folder/'temporal.json',summary)
    write(folder/'temporal-audit.json',ta)
    table.to_csv(folder/'temporal.csv')


def execute():
    p,_ = preflight()
    state = json.loads(STATE.read_text())
    if state['financial_attempts']:
        raise ValueError('No automatic financial retry/resume.')
    out = ROOT/('comparison-'+digest(PLAN)[:16])
    out.mkdir(exist_ok=False)
    state['comparison_plan_sha256'] = digest(PLAN)
    state['comparison_output'] = str(out)
    state['financial_attempts'] = [dict(id=c['id'],status='reserved') for c in CASES]
    write(STATE,state)
    write(out/'plan.json',p)
    started = time.monotonic()
    try:
        for i,item in enumerate(CASES):
            goal_left = 5400-(datetime.now(timezone.utc)-datetime.fromisoformat(state['started_utc'])).total_seconds()
            remaining = min(900-(time.monotonic()-started),goal_left)
            if remaining <= 0:
                raise TimeoutError('Financial or epoch bound exhausted.')
            state['financial_attempts'][i]['status'] = 'running'
            write(STATE,state)
            child = subprocess.run([sys.executable,'-m','research.multi_asset_comparison','--case',str(i),'--output',str(out)],
                                   capture_output=True,text=True,timeout=remaining)
            (out/(item['id']+'.log')).write_text(child.stdout+child.stderr)
            if child.returncode:
                raise RuntimeError('Financial case failed; preserved, no retry: '+item['id'])
            state['financial_attempts'][i]['status'] = 'completed'
            write(STATE,state)
        final_review(out)
        state['comparison_status'] = 'completed_reviewed'
    except Exception as error:
        for attempt in state['financial_attempts']:
            if attempt['status'] == 'running':
                attempt.update(status='failed',error=str(error))
        state['comparison_status'] = 'stopped_no_retry'
        raise
    finally:
        state['financial_elapsed_seconds'] = time.monotonic()-started
        write(STATE,state)
        write(out/'manifest.json',dict(status=state['comparison_status'],artifact_hashes={str(f.relative_to(out)):digest(f)
              for f in out.rglob('*') if f.is_file() and f.name != 'manifest.json'}))
        print(str(out))


def final_review(out):
    overall, annual = [], []
    for item in CASES:
        folder = out/item['id']
        scores = json.loads((folder/'scores.json').read_text())
        temporal = json.loads((folder/'temporal.json').read_text())
        curve = pd.read_csv(folder/'ledger.csv')
        row = dict(scores[0],rule=item['rule'],cost_bps=item['cost_bps'],
                   duration=temporal['longest_underwater_duration_sessions'],
                   recovery_censored=temporal['longest_underwater_right_censored'],
                   worst_21_return_pct=100*temporal['worst_returns']['21']['return'],
                   historical_daily_es95_pct=100*temporal['historical_daily_es95']['tail_mean_return'],
                   mean_exposure=float(curve.exposure.mean()),terminal_receivable=float(curve.receivable.iloc[-1]))
        overall.append(row)
        annual.extend(dict(score,rule=item['rule'],cost_bps=item['cost_bps']) for score in scores[1:])
    comparisons = []
    for cost in (5,25):
        rows = {r['rule']:r for r in overall if r['cost_bps']==cost}
        for rule in ('static_equal','trend_equal','relative_strength'):
            for reference in ('spy_entry_only','frozen_spy_gate'):
                a,b = rows[rule],rows[reference]
                gain = a['return_pct']-b['return_pct']
                depth = a['drawdown_pct']-b['drawdown_pct']
                duration = b['duration']-a['duration']
                passed = gain >= -1e-9 and depth >= -1e-9 and duration >= 0 and (gain > 1e-9 or depth > 1e-9 or duration > 0)
                comparisons.append(dict(rule=rule,reference=reference,cost_bps=cost,
                                        joint_claim_passed=passed,cagr_delta_pp=gain,
                                        drawdown_improvement_pp=depth,recovery_intervals_saved=duration))
    pd.DataFrame(overall).to_csv(out/'overall.csv',index=False)
    pd.DataFrame(annual).to_csv(out/'annual.csv',index=False)
    pd.DataFrame(comparisons).to_csv(out/'comparisons.csv',index=False)
    write(out/'decision.json',dict(comparisons=comparisons,
        conclusion='Report all growth/risk tradeoffs; only a rule passing both references at both costs satisfies the fixed joint claim.',
        historical_class='Development-only; source/restatement and execution limits apply. No automatic promotion.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--case',type=int,choices=range(10))
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if args.freeze:
        freeze()
    elif args.case is not None:
        case(args.case,args.output)
    elif args.execute:
        execute()
    else:
        load_bundle() if not PLAN.exists() else preflight()
        print('Qualified preflight passed; no financial path launched.')
