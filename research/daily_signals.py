"""Causal long/cash daily research rules. Contract: daily-strategies.md.

Signals are computed at completed closes and shifted exactly once to the next
row's open. These are fixed illustrative adaptations, not published alpha claims.
"""
import numpy as np
import pandas as pd


DEFINITIONS = {
    1: ('SMA crossover long/cash', {'fast': 50, 'slow': 200}),
    2: ('EMA crossover long/cash', {'fast': 50, 'slow': 200}),
    3: ('Price above SMA long/cash', {'period': 200}),
    4: ('MACD long/cash', {'fast': 12, 'slow': 26, 'signal': 9}),
    5: ('ADX-filtered SMA trend long/cash', {'adx_period': 14, 'adx_min': 25, 'sma_period': 200}),
    6: ('Donchian breakout long/cash', {'entry': 20, 'exit': 10}),
    7: ('Turtle-style channel long/cash adaptation', {'entry': 55, 'exit': 20}),
    8: ('ATR close breakout long/cash adaptation', {'atr_period': 14, 'atr_multiple': .5}),
    10: ('Prior-session high/low close breakout long/cash', {'lookback': 1}),
    11: ('RSI2 mean reversion long/cash', {'period': 2, 'entry_below': 10, 'exit_above': 50}),
    12: ('Bollinger mean reversion long/cash', {'period': 20, 'std_multiple': 2}),
    13: ('Close z-score mean reversion long/cash', {'period': 20, 'entry_below': -1.5, 'exit_at': 0}),
    14: ('Connors RSI mean reversion long/cash adaptation', {'price_rsi': 3, 'streak_rsi': 2, 'rank_period': 100, 'entry_below': 10, 'exit_above': 50}),
    15: ('Five-session return reversal long/cash', {'period': 5, 'entry_below': -.03, 'exit_at': 0}),
    21: ('Time-series momentum long/cash', {'lookback': 252}),
}


def _rsi(values, period):
    delta = values.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    result = 100 - 100 / (1 + gain / loss)
    return result.mask((gain == 0) & (loss == 0), 50)


def _state(entry, exit_, ready):
    held = False
    targets = []
    for enter, leave, available in zip(entry, exit_, ready):
        if not available:
            held = False
        elif held:
            if leave:
                held = False
        elif enter:
            held = True
        targets.append(held)
    return pd.Series(targets, index=entry.index, dtype=bool)


def _validate(raw):
    required = ['open', 'high', 'low', 'close']
    if not isinstance(raw, pd.DataFrame) or not set(required) <= set(raw):
        raise ValueError('Daily prices must contain open, high, low and close.')
    if (raw.empty or not isinstance(raw.index, pd.DatetimeIndex) or raw.index.hasnans
            or raw.index.has_duplicates or not raw.index.is_monotonic_increasing):
        raise ValueError('Daily dates must be nonempty, ordered, unique and valid.')
    prices = raw[required].astype(float)
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError('Prices must be finite and positive.')
    if ((prices.high < prices[['open', 'close', 'low']].max(axis=1)).any()
            or (prices.low > prices[['open', 'close', 'high']].min(axis=1)).any()):
        raise ValueError('OHLC range is inconsistent.')
    if 'volume' in raw:
        volume = raw.volume.to_numpy(dtype=float)
        if not np.isfinite(volume).all() or (volume < 0).any():
            raise ValueError('Volume must be finite and nonnegative.')
    return prices


def build_signal(raw: pd.DataFrame, strategy_id: int) -> pd.DataFrame:
    """Return open/low/close and bool want_long for next-open execution.

    Supply the full warm-up history before slicing the evaluation dates. Volume
    is optional because these rules do not consume it. Caller owns execution,
    sizing, dividends, costs and financing; this function never submits orders.
    """
    if strategy_id not in DEFINITIONS:
        raise ValueError(f'Unsupported daily strategy ID: {strategy_id}')
    data = _validate(raw)
    close, high, low = data.close, data.high, data.low
    target = None
    if strategy_id in (1, 2):
        if strategy_id == 1:
            fast, slow = close.rolling(50).mean(), close.rolling(200).mean()
        else:
            fast = close.ewm(span=50, adjust=False, min_periods=50).mean()
            slow = close.ewm(span=200, adjust=False, min_periods=200).mean()
        target = fast > slow
    elif strategy_id == 3:
        target = close > close.rolling(200).mean()
    elif strategy_id == 4:
        macd = (close.ewm(span=12, adjust=False, min_periods=12).mean()
                - close.ewm(span=26, adjust=False, min_periods=26).mean())
        signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
        target = macd > signal
    elif strategy_id in (5, 8):
        tr = pd.concat([high - low, (high - close.shift()).abs(),
                        (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        if strategy_id == 8:
            upper, lower = close.shift() + .5 * atr.shift(), close.shift() - .5 * atr.shift()
            target = _state(close > upper, close < lower, upper.notna())
        else:
            up, down = high.diff(), -low.diff()
            plus = up.where((up > down) & (up > 0), 0.).mask(up.isna())
            minus = down.where((down > up) & (down > 0), 0.).mask(down.isna())
            plus = plus.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / atr
            minus = minus.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / atr
            denominator = plus + minus
            dx = (100 * (plus - minus).abs() / denominator).mask(denominator == 0, 0.)
            adx = dx.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
            target = (close > close.rolling(200).mean()) & (adx >= 25)
    elif strategy_id in (6, 7, 10):
        entry_n, exit_n = {6: (20, 10), 7: (55, 20), 10: (1, 1)}[strategy_id]
        upper = high.shift().rolling(entry_n).max()
        lower = low.shift().rolling(exit_n).min()
        target = _state(close > upper, close < lower, upper.notna() & lower.notna())
    elif strategy_id == 11:
        rsi = _rsi(close, 2)
        target = _state(rsi < 10, rsi > 50, rsi.notna())
    elif strategy_id in (12, 13):
        mean, std = close.rolling(20).mean(), close.rolling(20).std(ddof=0)
        if strategy_id == 12:
            target = _state(close < mean - 2 * std, close >= mean, mean.notna())
        else:
            zscore = ((close - mean) / std).mask(std == 0, 0.)
            target = _state(zscore < -1.5, zscore >= 0, zscore.notna())
    elif strategy_id == 14:
        streak_values, streak = [], 0
        for change in close.diff():
            if pd.isna(change) or change == 0:
                streak = 0
            elif change > 0:
                streak = streak + 1 if streak > 0 else 1
            else:
                streak = streak - 1 if streak < 0 else -1
            streak_values.append(streak)
        streak_series = pd.Series(streak_values, index=close.index, dtype=float)
        rank = close.pct_change(fill_method=None).rolling(101).apply(
            lambda x: 100 * np.count_nonzero(x[:-1] < x[-1]) / 100, raw=True)
        crsi = (_rsi(close, 3) + _rsi(streak_series, 2) + rank) / 3
        target = _state(crsi < 10, crsi > 50, crsi.notna())
    elif strategy_id == 15:
        change = close.pct_change(5, fill_method=None)
        target = _state(change < -.03, change >= 0, change.notna())
    elif strategy_id == 21:
        target = close.pct_change(252, fill_method=None) > 0
    result = data[['open', 'low', 'close']].copy()
    result['want_long'] = target.shift(1, fill_value=False).astype(bool)
    return result
