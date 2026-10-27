"""Frozen causal allocation adaptations; contract: allocation-strategies.md.

Factors are completed-close decisions shifted once to the following open. CPPI
requires the portfolio ledger; this module cannot infer portfolio equity from SPY.
"""
import numpy as np
import pandas as pd

from research.policies.daily_signals import _validate


DEFINITIONS = {
    31: ('Volatility-targeted SPY allocation', {'vol_period': 20, 'target_vol': .10, 'annual_sessions': 252, 'factor_cap': 1.0}),
    32: ('EMA trend plus volatility-targeted SPY allocation', {'fast': 50, 'slow': 200, 'vol_period': 20, 'target_vol': .10, 'annual_sessions': 252, 'factor_cap': 1.0}),
    33: ('SPY-price drawdown-controlled allocation', {'warmup_closes': 20, 'half_exposure_drawdown': -.10, 'cash_drawdown_below': -.20}),
    34: ('CPPI fixed initial-capital floor allocation', {'floor_fraction': .8, 'multiplier': 3.0}),
}


def build_allocation_signal(raw: pd.DataFrame, strategy_id: int) -> pd.DataFrame:
    """Return next-open direction, lagged allocation factor, and CPPI knobs.

    Preserve full warm-up history before evaluation slicing. allocation_factor is
    in [0,1]; caller applies it to nominal exposure and owns costs and financing.
    CPPI uses constant metadata and must be interpreted by a portfolio-aware
    ledger using prior-close equity, never same-open or current-close equity.
    """
    if strategy_id not in DEFINITIONS:
        raise ValueError(f'Unsupported allocation strategy ID: {strategy_id}')
    data = _validate(raw)
    close = data.close
    result = data[['open', 'low', 'close']].copy()
    if strategy_id in (31, 32):
        returns = close.pct_change(fill_method=None)
        vol = returns.rolling(20, min_periods=20).std(ddof=1) * np.sqrt(252)
        # Zero observed variance uses the cap, never an infinite allocation.
        factor = (.10 / vol.where(vol > 0)).clip(upper=1).mask(vol == 0, 1).fillna(0)
        ready = vol.notna()
        target = ready
        if strategy_id == 32:
            fast = close.ewm(span=50, adjust=False, min_periods=50).mean()
            slow = close.ewm(span=200, adjust=False, min_periods=200).mean()
            target = ready & (fast > slow)
    elif strategy_id == 33:
        ready = close.rolling(20, min_periods=20).count() >= 20
        relative_price = close / close.cummax()
        factor = pd.Series(np.select([relative_price > .90, relative_price >= .80], [1., .5], default=0.), index=close.index)
        factor = factor.where(ready, 0.)
        target = ready & (factor > 0)
    else:
        factor = pd.Series(1., index=close.index)
        target = pd.Series(True, index=close.index)
        result['cppi_floor_fraction'] = .8
        result['cppi_multiplier'] = 3.
    result['want_long'] = target.shift(1, fill_value=False).astype(bool)
    result['allocation_factor'] = factor.shift(1, fill_value=0.).astype(float)
    return result
