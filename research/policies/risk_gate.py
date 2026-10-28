"""Fixed causal risk gate; protocol: docs/tasks/2026-10-25-risk-gate-bounded-test.md."""
import math
import pandas as pd
from research.policies.daily_signals import _validate, build_signal

CASES = ('hold','ema','gate_hold','gate_ema','half_hold','buy_hold_entry_only')
CAPS = {'unassessed':0.,'green':1.,'yellow':.5,'red':0.}


def states(features):
    """Close-observed state; recovery stages cannot share a confirmation close."""
    state='unassessed'; red_count=green_count=0; records=[]
    for _, row in features.iterrows():
        if not all(math.isfinite(float(row[k])) for k in ('fast','slow','vol','dd')):
            state='unassessed'; red_count=green_count=0; provisional='unassessed'
        else:
            positive=row.fast>row.slow
            red=row.dd<-.20 or row.vol>=.40
            yellow=not positive or row.dd<=-.10 or row.vol>=.25
            provisional='red' if red else ('yellow' if yellow else 'green')
            if state=='unassessed': state='yellow'
            if red:
                state='red'; red_count=green_count=0
            elif state=='red':
                red_count=red_count+1 if row.dd>-.18 and row.vol<.35 else 0
                green_count=0
                if red_count>=5: state='yellow'; red_count=0
            else:
                if state=='green' and yellow:
                    state='yellow'; green_count=0
                if state=='yellow':
                    green_count=green_count+1 if positive and row.dd>-.08 and row.vol<.20 else 0
                    if green_count>=5: state='green'; green_count=0
        records.append(dict(state=state,provisional=provisional,red_count=red_count,green_count=green_count,cap=CAPS[state]))
    return pd.DataFrame(records,index=features.index)


def timeline(raw):
    prices=_validate(raw)
    close=prices.close
    features=pd.DataFrame(dict(fast=close.ewm(span=50,adjust=False,min_periods=50).mean(),
                               slow=close.ewm(span=200,adjust=False,min_periods=200).mean(),
                               vol=close.pct_change().rolling(20,min_periods=20).std(ddof=1)*math.sqrt(252),
                               dd=close/close.cummax()-1))
    observed=features.join(states(features))
    observed['observed_close']=observed.index.astype(str)
    result=observed.shift(1)
    result['execution_open']=result.index.astype(str)
    return result


def frames(raw):
    """All targets already available at row's open. Do not shift again."""
    time=timeline(raw)
    ema=build_signal(raw,2).want_long.astype(bool)
    result={}
    for name in CASES:
        frame=raw[['open','low','close']].copy()
        base=ema.astype(float) if name in ('ema','gate_ema') else pd.Series(1.,index=raw.index)
        target=base.copy()
        if name.startswith('gate_'): target=pd.concat([base,time.cap.fillna(0)],axis=1).min(axis=1)
        if name=='half_hold': target*=.5
        frame['want_long']=target>0
        frame['allocation_factor']=target
        # Preserve the existing EMA control's nominal-budget diagnostic. Its
        # separate want_long flag sets cash exposure when the trend is off.
        if name=='ema': frame['allocation_factor']=1.
        if name=='buy_hold_entry_only': frame['rebalance_policy']='entry_only'
        frame['base_target']=base
        frame['intended_target']=target
        result[name]=frame
    return result,time
