"""Descriptive temporal diagnostics for an explicitly anchored equity path.

The first observation is initial capital before the first return interval; it is
not a trading session. Windows count observed return intervals, so the caller must
establish calendar completeness. Rolling returns are simple cumulative returns,
never annualized. Sharpe uses zero risk-free return, sample standard deviation
(ddof=1) and sqrt(252); standard deviation <=1e-15 in daily-return
fraction units is treated as numerically zero, matching reporting.annual.sharpe,
and has undefined Sharpe. This suppresses geometric-path floating roundoff.

Drawdown uses the initial anchor and running peaks. Episodes run from the latest
peak preceding a strictly underwater observation to first equity >= that peak,
or the final observation when unrecovered. Duration includes the recovery interval;
underwater_sessions separately counts observations strictly below the peak.
Calendar duration uses dates, not a fixed number of trading days. Longest episode
means most observed intervals, with calendar days as tie-breaker. It need not be
the deepest episode. Right-censoring is explicit and not an estimated recovery.

Historical daily ES95 is the arithmetic mean of the worst ceil(.05*n) observed
daily returns, without interpolation or an assumption of independent returns.
The actual tail fraction and count are reported; ties do not expand that count.
The loss sign is minus that mean, without clipping profitable tails to zero.
Small-sample warnings (<252 returns or <20 tail observations) are descriptive
reporting heuristics, not calibrated statistical acceptance or investment limits.
No statistic here is a future predictor, intervention signal or tail-risk bound.
"""
from __future__ import annotations

import math
from numbers import Real

import numpy as np
import pandas as pd

RETURN_WINDOWS = (21, 63, 126, 252)
SHARPE_WINDOWS = (63, 252)
WORST_WINDOWS = (1, 5, 21, 63)
SHARPE_ZERO_STD_ATOL = 1e-15


def _finite_or_none(value):
    return float(value) if value is not None and np.isfinite(value) else None


def _timestamp(value):
    return pd.Timestamp(value).isoformat()


def _rolling_sharpe(returns, window):
    # Incremental rolling variance can retain cancellation residue after a
    # volatile window has become entirely flat. Recompute each full window so
    # zero-variance cash periods remain undefined, not a misleading zero Sharpe.
    def ratio(values):
        sd = np.std(values, ddof=1)
        return np.mean(values) / sd * math.sqrt(252) if sd > SHARPE_ZERO_STD_ATOL else np.nan
    result = returns.rolling(window=window, min_periods=window).apply(ratio, raw=True)
    return result.replace([np.inf, -np.inf], np.nan)


def _episodes(equity, drawdown):
    result=[]
    start=None
    for i, dd in enumerate(drawdown):
        if dd < 0 and start is None:
            start=i-1
        if start is not None and (dd >= 0 or i == len(equity)-1):
            recovered=dd >= 0
            stop=i
            submerged_stop=stop if recovered else stop+1
            trough=start+1+int(np.argmin(equity.iloc[start+1:submerged_stop].to_numpy()))
            depth=float(equity.iloc[trough]/equity.iloc[start]-1)
            result.append({
                'peak_date':_timestamp(equity.index[start]),
                'trough_date':_timestamp(equity.index[trough]),
                'recovery_date':_timestamp(equity.index[stop]) if recovered else None,
                'observed_end_date':_timestamp(equity.index[stop]),
                'peak_equity':float(equity.iloc[start]),
                'trough_equity':float(equity.iloc[trough]),
                'drawdown':depth,
                'duration_sessions':int(stop-start),
                'underwater_sessions':int(stop-start-1 if recovered else stop-start),
                'duration_calendar_days':int((equity.index[stop].date()-equity.index[start].date()).days),
                'right_censored':not recovered,
            })
            start=None
    return result


def analyze_temporal(equity: pd.Series, *, initial_capital: float):
    """Return ``(JSON-safe summary, table)`` without modifying the input.

    ``equity`` needs a sorted unique DatetimeIndex and at least an explicit anchor
    plus one session. All equity values must be finite and strictly positive, and
    the first must exactly equal ``initial_capital``. Insolvent/invalid paths need
    their separate accounting report; they cannot be silently dropped or repaired.
    Table NaNs mean insufficient full-window coverage or undefined Sharpe, while
    corresponding summary values are JSON null.
    """
    if not isinstance(equity,pd.Series) or not isinstance(equity.index,pd.DatetimeIndex):
        raise ValueError('Equity must be a Series with an explicit DatetimeIndex.')
    if len(equity)<2 or equity.index.hasnans or equity.index.has_duplicates or not equity.index.is_monotonic_increasing:
        raise ValueError('Need an anchor and sorted, unique, valid session dates.')
    if isinstance(initial_capital,bool) or not isinstance(initial_capital,Real) or not math.isfinite(initial_capital) or initial_capital<=0:
        raise ValueError('Initial capital must be finite and strictly positive.')
    if not pd.api.types.is_numeric_dtype(equity) or pd.api.types.is_bool_dtype(equity) or pd.api.types.is_complex_dtype(equity):
        raise ValueError('Equity must be numeric, not boolean or coerced text.')
    values=equity.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values<=0).any():
        raise ValueError('Equity must be finite and strictly positive throughout.')
    if values[0]!=float(initial_capital):
        raise ValueError('First equity observation must be the explicit initial-capital anchor.')
    eq=pd.Series(values.copy(),index=equity.index.copy(),name='equity_usd')
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        daily=eq.pct_change(fill_method=None)
    if not np.isfinite(daily.iloc[1:]).all():
        raise ValueError('Equity ratios exceed the finite numerical return domain.')
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        total_return=float(eq.iloc[-1]/eq.iloc[0]-1)
    if not math.isfinite(total_return):
        raise ValueError('Total equity ratio exceeds the finite numerical return domain.')
    dd=eq.div(eq.cummax()).sub(1)
    table=pd.DataFrame({'equity_usd':eq,'daily_return':daily,'drawdown':dd})
    rolling_summary={}
    for window in RETURN_WINDOWS:
        with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
            r=eq.div(eq.shift(window)).sub(1)
        if not np.isfinite(r.iloc[window:]).all():
            raise ValueError('Rolling equity ratios exceed the finite numerical return domain.')
        table[f'return_{window}']=r
        rolling_summary[str(window)]={
            'window_sessions':window,'full_coverage_required':True,'valid_windows':int(r.notna().sum()),
            'minimum_return':_finite_or_none(r.min()),'maximum_return':_finite_or_none(r.max()),
            'last_return':_finite_or_none(r.iloc[-1]),
        }
    sharpe_summary={}
    for window in SHARPE_WINDOWS:
        r=_rolling_sharpe(daily,window)
        table[f'sharpe_{window}']=r
        sharpe_summary[str(window)]={'window_sessions':window,'full_coverage_required':True,
                                    'valid_windows':int(r.notna().sum()),'minimum_sharpe':_finite_or_none(r.min()),
                                    'maximum_sharpe':_finite_or_none(r.max()),'last_sharpe':_finite_or_none(r.iloc[-1]),
                                    'risk_free_rate':0.,'sessions_per_year':252,'standard_deviation_ddof':1,
                                    'numerical_zero_std_atol':SHARPE_ZERO_STD_ATOL}
    episodes=_episodes(eq,dd)
    worst=min(episodes,key=lambda e:e['drawdown']) if episodes else None
    longest=max(episodes,key=lambda e:(e['duration_sessions'],e['duration_calendar_days'])) if episodes else None
    worst_returns={}
    for window in WORST_WINDOWS:
        with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
            r=eq.div(eq.shift(window)).sub(1)
        if not np.isfinite(r.iloc[window:]).all():
            raise ValueError('Worst-window equity ratios exceed the finite numerical return domain.')
        available=r.dropna()
        if available.empty:
            worst_returns[str(window)]={'window_sessions':window,'valid_windows':0,'return':None,'start_date':None,'end_date':None}
        else:
            end=r.index.get_loc(available.idxmin())
            worst_returns[str(window)]={'window_sessions':window,'valid_windows':int(len(available)),
                                       'return':float(r.iloc[end]),'start_date':_timestamp(eq.index[end-window]),
                                       'end_date':_timestamp(eq.index[end])}
    n=len(eq)-1
    k=math.ceil(.05*n)
    tail=daily.iloc[1:].nsmallest(k)
    tail_mean=float(tail.mean())
    warnings=[]
    if n<252:warnings.append('Fewer than 252 observed daily return intervals.')
    if k<20:warnings.append('Fewer than 20 empirical tail observations; ES is especially unstable.')
    summary={
        'method_version':'temporal-v1.2','anchor_date':_timestamp(eq.index[0]),
        'initial_capital':float(initial_capital),'last_date':_timestamp(eq.index[-1]),
        'observed_sessions':n,'total_return':total_return,
        'max_drawdown':float(dd.min()),'drawdown_is_signed_fraction':True,
        'rolling_returns':rolling_summary,'rolling_sharpe':sharpe_summary,
        'worst_returns':worst_returns,'worst_drawdown_episode':worst,
        'longest_underwater_episode':longest,
        'longest_underwater_duration_sessions':longest['duration_sessions'] if longest else 0,
        'longest_underwater_duration_calendar_days':longest['duration_calendar_days'] if longest else 0,
        'longest_underwater_right_censored':longest['right_censored'] if longest else False,
        'drawdown_episodes':episodes,
        'historical_daily_es95':{'confidence_level':.95,'definition':'mean of worst ceil(.05*n) observed daily simple returns',
                                 'sample_count':n,'tail_count':k,'actual_tail_fraction':k/n,
                                 'tail_mean_return':tail_mean,'loss_magnitude':-tail_mean,
                                 'threshold_return':float(tail.max()),'small_sample':bool(warnings),
                                 'warnings':warnings,'independence_assumed':False,
                                 'future_loss_bound':False},
        'coverage_note':'Windows count observed intervals; exchange-calendar completeness is caller-verified.',
    }
    return summary,table
