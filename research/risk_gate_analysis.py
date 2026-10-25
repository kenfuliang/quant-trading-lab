"""Post-hoc event attribution. Future event outcomes never enter the gate."""
import math
import numpy as np
import pandas as pd
from scripts.recursive_research_review import metrics


def independent_temporal(equity, summary, table):
    """Second implementation: scalar peak scan + explicit rolling windows."""
    a=np.asarray(equity,float); peak=a[0]; start=0; durations=[]
    for i in range(1,len(a)):
        if a[i]>=peak:
            if a[i-1]<peak: durations.append(i-start)
            peak=a[i]; start=i
        elif i==len(a)-1: durations.append(i-start)
    longest=max(durations,default=0)
    observed=summary['longest_underwater_episode']
    assert longest==(observed['duration_sessions'] if observed else 0)
    checks=1
    for w in (21,63,126,252):
        expected=np.array([a[i]/a[i-w]-1 for i in range(w,len(a))])
        np.testing.assert_allclose(table[f'return_{w}'].iloc[w:],expected,atol=1e-12,rtol=0)
        checks+=len(expected)
    returns=np.diff(a)/a[:-1]
    for w in (63,252):
        expected=[]
        for i in range(w,len(a)):
            x=returns[i-w:i]; sd=np.std(x,ddof=1)
            expected.append(np.mean(x)/sd*math.sqrt(252) if sd>1e-15 else np.nan)
        np.testing.assert_allclose(table[f'sharpe_{w}'].iloc[w:],expected,atol=1e-7,rtol=1e-9,equal_nan=True)
        checks+=len(expected)
    for w in (1,5,21,63):
        x=min(a[i]/a[i-w]-1 for i in range(w,len(a)))
        assert abs(x-summary['worst_returns'][str(w)]['return'])<1e-12
        checks+=1
    tail=sorted(float(x) for x in returns)[:math.ceil(.05*len(returns))]
    es=summary['historical_daily_es95']
    assert len(tail)==es['tail_count'] and abs(sum(tail)/len(tail)-es['tail_mean_return'])<1e-12
    checks+=1
    return dict(passed=True,scalar_and_window_checks=checks,longest_duration_sessions=longest)


def blocks(curve, capital, ranges):
    eq=curve.equity_usd
    rows=[]
    for start,end in ranges:
        g=eq.loc[start:end]; pos=eq.index.get_loc(g.index[0]); anchor=eq.iloc[pos-1] if pos else capital
        rows.append(dict(start=start,end=end,anchor_equity=float(anchor),sessions=len(g),**metrics(np.r_[anchor,g])))
    return rows


def events(time, frame, gate, base, hold, capital):
    """Executed states, warnings and red entry/exit outcome windows, censoring retained."""
    n=len(frame); colors=time.state.tolist(); dates=frame.index.tolist()
    warnings=[]; transitions=[]; windows=[]; episode=None
    def outcome(i,h,series):
        if i+h>n: return None
        anchor=capital if i==0 else float(series.iloc[i-1])
        return float(series.iloc[i+h-1]/anchor-1)
    for i,color in enumerate(colors):
        previous=colors[i-1] if i else None
        if previous!=color:
            transitions.append(dict(date=dates[i],previous=previous,state=color,left_censored=(i==0)))
            if previous=='green' and color in ('yellow','red'):
                episode=dict(start=dates[i],start_index=i,end=None,left_censored=False,actionable_index=None)
                warnings.append(episode)
            elif i==0 and color in ('yellow','red'):
                episode=dict(start=dates[i],start_index=i,end=None,left_censored=True,actionable_index=None)
                warnings.append(episode)
            if color=='green' and episode is not None:
                episode['end']=dates[i]; episode=None
            if i and (color=='red' or previous=='red'):
                for h in (5,21,63):
                    g=outcome(i,h,gate.equity_usd); b=outcome(i,h,base.equity_usd); v=outcome(i,h,hold.equity_usd)
                    windows.append(dict(date=dates[i],event='red_entry' if color=='red' else 'red_exit',horizon=h,
                        right_censored=g is None,gate_return=g,base_return=b,hold_return=v,
                        base_minus_gate=None if g is None else b-g,hold_minus_gate=None if g is None else v-g,
                        mean_actual_close_exposure=None if g is None else float((gate.shares*gate.close/gate.equity_usd).iloc[i:i+h].mean()),
                        gate_cost_usd=None if g is None else float((gate.commission_usd+gate.slippage_usd).iloc[i:i+h].sum())))
        if episode is not None and episode['actionable_index'] is None and frame.intended_target.iloc[i]<frame.base_target.iloc[i]:
            episode['actionable_index']=i
    for e in warnings:
        for prefix,i in [('warning',e['start_index']),('actionable',e['actionable_index'])]:
            e[prefix+'_date']=dates[i] if i is not None else None
            censored=i is not None and i+21>n
            e[prefix+'_right_censored']=censored
            e[prefix+'_price_drop_5pct']=None if i is None or censored else bool((frame.close.iloc[i:i+21]<=.95*frame.open.iloc[i]).any())
            hits=[] if i is None or censored else np.flatnonzero(frame.close.iloc[i:i+21].to_numpy()<=.95*frame.open.iloc[i])
            e[prefix+'_first_drop_offset_sessions']=int(hits[0]) if len(hits) else None
        e['episode_right_censored']=e['end'] is None
        e['action_delay_sessions']=None if e['actionable_index'] is None else e['actionable_index']-e['start_index']
    eligible=[e for e in warnings if not e['left_censored'] and e['warning_price_drop_5pct'] is not None]
    action=[e for e in warnings if e['actionable_price_drop_5pct'] is not None and not e['left_censored']]
    starts=[e['start_index'] for e in eligible]
    return dict(warnings=warnings,transitions=transitions,red_windows=windows,
                state_dwell={str(k):int(v) for k,v in pd.Series(colors).value_counts().items()},
                summary=dict(warning_episodes=len(warnings),left_censored=sum(e['left_censored'] for e in warnings),
                    evaluable_warning_episodes=len(eligible),warnings_with_drop=sum(e['warning_price_drop_5pct'] for e in eligible),
                    false_alarm_episodes=sum(not e['warning_price_drop_5pct'] for e in eligible),
                    warning_precision=None if not eligible else sum(e['warning_price_drop_5pct'] for e in eligible)/len(eligible),
                    actionable_episodes=len(action),actionable_with_drop=sum(e['actionable_price_drop_5pct'] for e in action),
                    overlapping_warning_horizons=sum(b-a<21 for a,b in zip(starts,starts[1:]))))
