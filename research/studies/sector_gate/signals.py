"""Retained EMA/volatility-only gate; 2016-source warmup, next-open execution.

Thresholds and five-close staged recovery mirror risk_gate.states with dd=0.
The expanding-price-peak component is deliberately disabled, as in the retained
price-peak ablation. No fit, training, search or outcome labels are consulted.
"""
import math
import pandas as pd


def classify(features):
    state='unassessed';red_count=green_count=0;rows=[]
    for _,r in features.iterrows():
        if not all(math.isfinite(float(r[k])) for k in ('fast','slow','vol')):
            state='unassessed';red_count=green_count=0;provisional='unassessed'
        else:
            positive=r.fast>r.slow;red=r.vol>=.40;yellow=not positive or r.vol>=.25
            provisional='red' if red else ('yellow' if yellow else 'green')
            if state=='unassessed':state='yellow'
            if red:state='red';red_count=green_count=0
            elif state=='red':
                red_count=red_count+1 if r.vol<.35 else 0;green_count=0
                if red_count>=5:state='yellow';red_count=0
            else:
                if state=='green' and yellow:state='yellow';green_count=0
                if state=='yellow':
                    green_count=green_count+1 if positive and r.vol<.20 else 0
                    if green_count>=5:state='green';green_count=0
        rows.append(dict(state=state,provisional=provisional,red_count=red_count,green_count=green_count,
                         cap={'unassessed':0.,'red':0.,'yellow':.5,'green':1.}[state]))
    return pd.DataFrame(rows,index=features.index)


def timeline(close):
    if not close.index.is_monotonic_increasing or close.index.has_duplicates or not (close>0).all():raise ValueError('Invalid gate prices.')
    features=pd.DataFrame(dict(fast=close.ewm(span=50,adjust=False,min_periods=50).mean(),
        slow=close.ewm(span=200,adjust=False,min_periods=200).mean(),
        vol=close.pct_change().rolling(20,min_periods=20).std(ddof=1)*math.sqrt(252)))
    observed=features.join(classify(features));observed['decision_close']=observed.index.strftime('%Y-%m-%d')
    return observed.shift(1)
