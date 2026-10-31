"""Last two predeclared synthetic native checks; no historical prices or trials."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd

from research.multi_asset import SYMBOLS
from research.native_multi_asset import run_native
from research.multi_asset_cash_audit import reconcile
from research.multi_asset_accounting_probe import write

STATE = Path('.local/multi-asset-qualification-v2/state.json')
PLAN = STATE.parent/'accounting-stress-plan.json'
CASES = ('rotation_25bp','same_day_rounding_25bp')
CODE = ('research/multi_asset_accounting_stress.py','research/native_multi_asset.py',
        'research/multi_asset_cash_audit.py','research/multi_asset.py','research/us_etf_calendar.py',
        'research/multi_asset_accounting_probe.py','requirements.lock.txt')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    state = json.loads(STATE.read_text())
    if len(state['native_probes']) != 2 or not all(a['status']=='completed' for a in state['native_probes']):
        raise ValueError('Require the two completed base proofs; no retry/reservation reset.')
    with PLAN.open('x') as stream:
        json.dump(dict(cases=CASES,cost_bps=25,synthetic_only=True,
                       total_epoch_native_ceiling=4,code_hashes={p:digest(p) for p in CODE},
                       purpose='Verify primary25bp execution context and same-ex/pay-date cent rounding before historical launch.'),stream,indent=2)
        stream.write('\n')


def execute():
    plan = json.loads(PLAN.read_text())
    if plan['code_hashes'] != {p:digest(p) for p in CODE}:
        raise ValueError('Frozen synthetic stress identity changed.')
    state = json.loads(STATE.read_text())
    count = len(state['native_probes'])
    if count not in (2,3) or state['native_probe_limit'] != 4:
        raise ValueError('Four-probe epoch budget exhausted or invalid.')
    if not all(a['status']=='completed' for a in state['native_probes']):
        raise ValueError('Preserve failed probe; no automatic continuation.')
    if datetime.now(timezone.utc) >= datetime.fromisoformat(state['deadline_utc']):
        raise ValueError('Epoch deadline expired.')
    name = CASES[count-2]
    out = STATE.parent/('accounting-'+name)
    out.mkdir(exist_ok=False)
    for source in CODE:
        (out/('source-'+source.replace('/','_'))).write_bytes(Path(source).read_bytes())
    attempt = dict(case=name,status='reserved',output=str(out),plan_sha256=digest(PLAN),
                   started_utc=datetime.now(timezone.utc).isoformat(),code_hashes=plan['code_hashes'])
    state['native_probes'].append(attempt)
    write(STATE,state)
    try:
        dates = pd.Index(['2020-01-02','2020-01-03','2020-01-06'],name='date')
        if name == 'rotation_25bp':
            prices = dict(SPY=[100,100,100],IEF=[50,48,48],GLD=[25,25,25])
            targets = {dates[0]:{s:1/3 for s in SYMBOLS}, dates[1]:dict(SPY=0,IEF=0,GLD=1)}
            actions = [dict(id='IEF-fixture',symbol='IEF',ex_date=dates[1],pay_date=dates[2],amount='2')]
        else:
            prices = dict(SPY=[100,99.88,99.88],IEF=[50,50,50],GLD=[25,25,25])
            targets = {dates[0]:dict(SPY=1,IEF=0,GLD=0),dates[1]:{s:0 for s in SYMBOLS}}
            actions = [dict(id='SPY-fixture',symbol='SPY',ex_date=dates[1],pay_date=dates[1],amount='0.123456')]
        frames = {s:pd.DataFrame(dict(open=prices[s],close=prices[s]),index=dates) for s in SYMBOLS}
        curve,trades,events = run_native(frames,targets,actions,capital=1000,cost_bps=25)
        curve.to_csv(out/'ledger.csv')
        trades.to_csv(out/'trades.csv',index=False)
        write(out/'events.json',events)
        audit = reconcile(frames,targets,actions,curve,trades,events,capital=1000,cost_bps=25)
        if name == 'rotation_25bp':
            assert audit['fills']==6 and curve.iloc[-1]['GLD']==38 and curve.iloc[-1]['cash']==38.78
        else:
            assert audit['fills']==2 and curve.iloc[-1]['cash']==993.53
            assert events[1]['cash_credit']=='1.11' and events[1]['rounding_pnl']=='-0.001104'
            assert curve.iloc[-1]['SPY']==0 and curve.iloc[-1]['receivable']==0
        write(out/'proof.json',dict(synthetic_only=True,historical_financial_attempts=0,case=name,cost_bps=25,audit=audit))
        attempt['status']='completed'
    except Exception as error:
        attempt.update(status='failed',error=str(error))
        write(out/'failure.json',attempt)
        raise
    finally:
        write(STATE,state)
        write(out/'manifest.json',dict(artifact_hashes={p.name:digest(p) for p in out.iterdir()
              if p.is_file() and p.name!='manifest.json'}))
        print(str(out))


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true')
    args=parser.parse_args()
    freeze() if args.freeze else execute()
