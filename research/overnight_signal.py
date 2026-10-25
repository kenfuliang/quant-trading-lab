"""Precommitted close-to-next-open exposure; contract: overnight-strategy.md."""
import pandas as pd

from research.daily_signals import _validate


DEFINITIONS = {
    19: ('Precommitted SPY close-to-next-open long exposure adaptation',
         {'entry': 'each_session_close', 'exit': 'next_session_open',
          'execution_schedule': 'overnight', 'signal_warmup_sessions': 1}),
}


def build_overnight_signal(raw: pd.DataFrame, strategy_id: int = 19) -> pd.DataFrame:
    """Return predetermined exposure flags and an explicit overnight schedule.

    Unlike ordinary daily signals, the execution schedule requires the portfolio
    ledger to exit at the open and enter at the close. A constant exposure plan
    is shifted once for the shared interface; current close never selects entry.
    Pass full warm-up history before slicing evaluation dates. No order is sent.
    """
    if strategy_id != 19:
        raise ValueError(f'Unsupported overnight strategy ID: {strategy_id}')
    prices = _validate(raw)
    result = prices[['open', 'low', 'close']].copy()
    result['want_long'] = pd.Series(True, index=prices.index).shift(1, fill_value=False)
    result['execution_schedule'] = 'overnight'
    return result
