"""Two finite native synthetic accounting cases for the qualification epoch."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd
from research.studies.checkpoint_20261031.native_multi_asset import run_native
from research.studies.checkpoint_20261031.multi_asset_cash_audit import reconcile
from research.studies.checkpoint_20261031.multi_asset import SYMBOLS

STATE = Path('.local/multi-asset-qualification-v2/state.json')


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def run_case(name, out):
    dates = pd.Index(['2020-01-02', '2020-01-03', '2020-01-06'], name='date')
    prices = dict(SPY=[100,100,100], IEF=[50,48,48], GLD=[25,25,25])
    if name == 'terminal':
        prices = dict(SPY=[100,99.88,99.88], IEF=[50,50,50], GLD=[25,25,25])
    frames = {s: pd.DataFrame(dict(open=prices[s], close=prices[s]), index=dates) for s in SYMBOLS}
    if name == 'rotation':
        targets = {dates[0]: {s: 1/3 for s in SYMBOLS}, dates[1]: dict(SPY=0, IEF=0, GLD=1)}
        actions = [dict(id='IEF-fixture', symbol='IEF', ex_date=dates[1], pay_date=dates[2], amount='2')]
    elif name == 'terminal':
        targets = {dates[0]: dict(SPY=1, IEF=0, GLD=0)}
        actions = [dict(id='SPY-fixture', symbol='SPY', ex_date=dates[1], pay_date='2020-01-31', amount='0.123456')]
    else:
        raise ValueError('Unknown synthetic accounting case.')
    curve, trades, events = run_native(frames, targets, actions, capital=1000, cost_bps=5)
    curve.to_csv(out/'ledger.csv')
    trades.to_csv(out/'trades.csv', index=False)
    write(out/'events.json', events)
    audit = reconcile(frames, targets, actions, curve, trades, events, capital=1000, cost_bps=5)
    if name == 'rotation':
        assert audit['fills'] == 6 and audit['terminal_receivable_usd'] == '0'
        assert [row['kind'] for row in events] == ['entitlement', 'payment']
    else:
        assert audit['fills'] == 1 and audit['terminal_receivable_usd'] == '1.111104'
        assert len(events) == 1 and float(curve.iloc[-1].receivable) > 0
    write(out/'proof.json', dict(synthetic_only=True, historical_financial_attempts=0, case=name, audit=audit))


def main():
    state = json.loads(STATE.read_text())
    if len(state['native_probes']) >= 2:
        raise ValueError('Two fixed accounting cases already consumed; no automatic retry.')
    if (datetime.now(timezone.utc)-datetime.fromisoformat(state['started_utc'])).total_seconds() >= 5400:
        raise ValueError('Deadline expired.')
    name = ('rotation','terminal')[len(state['native_probes'])]
    out = STATE.parent/f'accounting-{name}'
    out.mkdir(exist_ok=False)
    sources = ('research/native_multi_asset.py','research/multi_asset_cash_audit.py','research/multi_asset.py',
               'research/us_etf_calendar.py','research/multi_asset_accounting_probe.py','requirements.lock.txt')
    for source in sources:
        (out/('source-'+source.replace('/','_'))).write_bytes(Path(source).read_bytes())
    attempt = dict(case=name, status='reserved', output=str(out), started_utc=datetime.now(timezone.utc).isoformat(),
                   code_hashes={p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources})
    state['native_probes'].append(attempt)
    write(STATE, state)
    try:
        run_case(name, out)
        attempt['status'] = 'completed'
    except Exception as error:
        attempt.update(status='failed', error=str(error))
        write(out/'failure.json', attempt)
        raise
    finally:
        write(STATE, state)
        write(out/'manifest.json', dict(artifact_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in out.iterdir() if p.is_file() and p.name != 'manifest.json'}))
        print(str(out))


if __name__ == '__main__':
    main()
