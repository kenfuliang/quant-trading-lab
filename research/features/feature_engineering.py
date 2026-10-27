"""Causal fixed feature registry and descriptive diagnostics, not trading rules."""
import numpy as np
import pandas as pd

VERSION = 'spy-feature-diagnostic-v1'
REGISTRY = [
    dict(id='vol_ratio20_60', family='risk_dynamics', units='ratio', fields=['close'],
         formula='sample_std20(simple_close_return)/sample_std60(simple_close_return)',
         mechanism='Recent volatility relative to a slower risk baseline', minimum_closes=61,
         provenance='Assistant proposal; prior conversation ratio idea; risk-sizing literature'),
    dict(id='ema_gap_pct', family='trend_strength', units='fraction', fields=['close'],
         formula='EMA50(adjustFalse,min50)/EMA200(adjustFalse,min200)-1',
         mechanism='Continuous trend distance beyond binary crossover', minimum_closes=200,
         provenance='Assistant proposal; existing EMA input and Qlib moving-average family'),
    dict(id='range20_pct', family='range_risk', units='fraction', fields=['high','low','close'],
         formula='mean20((high-low)/close)',
         mechanism='Recent daily price range as a separate risk proxy', minimum_closes=20,
         provenance='Assistant proposal; Qlib range geometry family, not literal Alpha158 replication'),
]
FEATURES = [r['id'] for r in REGISTRY]
BASELINES = ['sigma20', 'ema_positive']


def validate_prices(raw):
    if not isinstance(raw.index, pd.DatetimeIndex) or raw.index.has_duplicates or not raw.index.is_monotonic_increasing or raw.index.hasnans:
        raise ValueError('Ordered unique dated prices required.')
    a = raw[['open','high','low','close']].to_numpy(float)
    if (not np.isfinite(a).all() or (a <= 0).any()
            or (raw.high < raw[['open','low','close']].max(axis=1)).any()
            or (raw.low > raw[['open','high','close']].min(axis=1)).any()):
        raise ValueError('Invalid OHLC values; no silent repair.')


def build_features(raw):
    """All values at row t use completed bars strictly before t."""
    validate_prices(raw)
    r = raw.close.pct_change(fill_method=None)
    s20 = r.rolling(20,min_periods=20).std(ddof=1)
    s60 = r.rolling(60,min_periods=60).std(ddof=1)
    fast = raw.close.ewm(span=50,adjust=False,min_periods=50).mean()
    slow = raw.close.ewm(span=200,adjust=False,min_periods=200).mean()
    f = pd.DataFrame({
        'vol_ratio20_60': s20 / s60.where(s60 > 0),
        'ema_gap_pct': fast / slow - 1,
        'range20_pct': ((raw.high-raw.low)/raw.close).rolling(20,min_periods=20).mean(),
        'sigma20':s20*np.sqrt(252),
        'ema_positive':(fast>slow).astype(float).where(fast.notna() & slow.notna()),
    }, index=raw.index).shift(1)
    f['observed_close'] = pd.Series(raw.index,index=raw.index).shift(1)
    return f


def future_risk(raw, horizon=21):
    """Outcome only: realized volatility including decision-session overnight gap."""
    validate_prices(raw)
    if type(horizon) is not int or horizon < 2:
        raise ValueError('At least two return observations required.')
    r = raw.close.pct_change(fill_method=None)
    return r.rolling(horizon,min_periods=horizon).std(ddof=1).shift(-(horizon-1))*np.sqrt(252)


def rank_association(x, y):
    z = pd.concat([x.rename('x'),y.rename('y')],axis=1).dropna()
    if not np.isfinite(z.to_numpy(float)).all():
        raise ValueError('Nonfinite association inputs.')
    reason = 'fewer_than_three_pairs' if len(z)<3 else ('constant_input' if min(z.nunique())<2 else None)
    return dict(n=len(z),spearman=None if reason else float(z.x.rank().corr(z.y.rank())),undefined_reason=reason)


def fit_edges(values):
    clean=values.dropna()
    if len(clean)<3 or not np.isfinite(clean.to_numpy(float)).all():
        raise ValueError('Finite calibration observations required.')
    edges=np.quantile(clean.to_numpy(float),[1/3,2/3])
    if edges[0]>=edges[1]:
        return None
    return [float(x) for x in edges]


def assign_bins(values, edges):
    if edges is None:
        return pd.Series('undefined_constant_calibration',index=values.index)
    if len(edges)!=2 or not np.isfinite(edges).all() or edges[0]>=edges[1]:
        raise ValueError('Two ordered finite calibration edges required.')
    result=pd.Series(np.where(values<=edges[0],'low',np.where(values<=edges[1],'middle','high')),index=values.index)
    result.loc[values.isna()]='undefined_missing'
    return result


def mature_within(rows, start, end):
    """Do not shorten target horizons or let outcomes cross a period boundary."""
    return rows.loc[(rows.index>=pd.Timestamp(start)) & (rows.index<=pd.Timestamp(end))
                    & rows.label_available_after_close.notna()
                    & (rows.label_available_after_close<=pd.Timestamp(end))
                    & ~rows.right_censored].copy()
