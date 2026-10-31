"""Read-only feature preview. Not an armed strategy or execution adapter."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import math
import runpy

import pandas as pd
from research.risk_gate import states
from research.studies.t11_reproduction.indicators import WilderRSI, SimpleAverage
from paper_trading.t11_pilot import SYMBOLS, POLICY_HASH

NY=ZoneInfo('America/New_York')
R10=('SPY','IOO','TQQQ','VTV','XLF','XLK','KMLM','PSQ','BND','QQQ','IEF')
R20=('TLT','PSQ','AGG')


def close_map(payloads, symbols, expected):
    result={s:{} for s in symbols}
    for payload in payloads:
        if not isinstance(payload.get('bars'),dict):raise ValueError('Missing bars container.')
        for symbol,bars in payload['bars'].items():
            if symbol not in result:raise ValueError('Unexpected symbol.')
            for bar in bars:
                ts=datetime.fromisoformat(bar['t'].replace('Z','+00:00'))
                if ts.tzinfo is None:raise ValueError('Timezone required.')
                local=ts.astimezone(NY);day=local.date().isoformat()
                if local.strftime('%H:%M:%S')!='00:00:00' or day not in expected or day in result[symbol]:raise ValueError('Unexpected/duplicate bar session.')
                vals=[float(bar[k]) for k in ('o','h','l','c','v')]
                if not all(math.isfinite(v) for v in vals) or min(vals[:4])<=0 or vals[4]<0:raise ValueError('Invalid OHLCV.')
                o,h,l,c,_=vals
                if not l<=min(o,c)<=max(o,c)<=h:raise ValueError('Invalid OHLC ordering.')
                result[symbol][day]=c
    for symbol,rows in result.items():
        if set(rows)!=set(expected):raise ValueError('Missing completed sessions: '+symbol)
    return result


def features(closes, sessions):
    if set(closes)!=SYMBOLS or len(sessions)<215:raise ValueError('Need full215-session universe.')
    def indicator(kind,symbol,period):
        obj=kind(period)
        for day in sessions:obj.update(closes[symbol][day])
        if not obj.ready:raise ValueError('Indicator is unready.')
        return float(obj.current)
    return {'rsi10':{s:indicator(WilderRSI,s,10) for s in R10},
            'rsi20':{s:indicator(WilderRSI,s,20) for s in R20},
            'rsi60_sh':indicator(WilderRSI,'SH',60),
            'prices':{s:closes[s][sessions[-1]] for s in ('SPY','TQQQ','KMLM')},
            'sma200_spy':indicator(SimpleAverage,'SPY',200),
            'sma20_tqqq':indicator(SimpleAverage,'TQQQ',20),
            'sma20_kmlm':indicator(SimpleAverage,'KMLM',20),
            'qqq_history':[closes['QQQ'][d] for d in sessions[-61:]],
            'core_ready':True,'kmlm_ready':True}


def gate_preview(raw_spy):
    """Local operational seed stability check, not the original2004 LEAN seed."""
    if len(raw_spy)<500:raise ValueError('Need at least500 raw sessions.')
    def calculate(items):
        close=pd.Series([round(float(v),2) for _,v in items],index=[d for d,_ in items])
        if not all(math.isfinite(x) and x>0 for x in close):raise ValueError('Invalid gate close.')
        fast=close.ewm(span=50,adjust=False).mean();slow=close.ewm(span=200,adjust=False).mean()
        vol=close.pct_change().rolling(20).std(ddof=1)*math.sqrt(252)
        fast.iloc[:199]=float('nan');slow.iloc[:199]=float('nan')
        f=pd.DataFrame({'fast':fast,'slow':slow,'vol':vol,'dd':0.})
        scored=states(f)
        return scored,fast,slow,vol
    items=sorted(raw_spy.items())
    full,fast,slow,vol=calculate(items)
    short,_,_,_=calculate(items[len(items)//2:])
    stable=full.tail(60)['state'].tolist()==short.tail(60)['state'].tolist()
    return {'state':str(full.iloc[-1]['state']),'cap':float(full.iloc[-1]['cap']),
            'fast':float(fast.iloc[-1]),'slow':float(slow.iloc[-1]),'vol':float(vol.iloc[-1]),
            'seed_sessions':len(items),'last60_states_match_half_seed':stable,
            'original2004_seed_parity':False}


def pinned_policy(path, feature_values, cap):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=POLICY_HASH:raise ValueError('Private policy hash mismatch.')
    # Exact previously inspected private pure-policy module. Never execute a
    # source supplied by a web page or an unpinned arbitrary module.
    return runpy.run_path(str(path))['decide'](feature_values,cap)
