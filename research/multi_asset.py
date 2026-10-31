"""Pure research signals and native-order planning seam; no data fetch or broker I/O.

Historical eligibility is a separate prerequisite. These functions do not certify
provider data, keep execution state, or implement native corporate actions.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN
import math

import numpy as np
import pandas as pd

SYMBOLS = ('GLD', 'IEF', 'SPY')  # permanent tie-break and execution order
D = lambda value: Decimal(str(value))


def forward_total_return(raw_closes, distributions, split_ratios):
    """Causal index for verified unadjusted closes and explicit action ordering.

    Distributions are cash per post-split share on the ex-date. Apply split ratio
    (new shares per old) before that date's distribution. A qualified source must
    establish this convention; it is not a Yahoo-field assumption. Payment dates
    affect separate spendable cash and never add to this index a second time.
    """
    if (not isinstance(raw_closes, pd.Series) or not isinstance(raw_closes.index, pd.DatetimeIndex) or
            raw_closes.empty or raw_closes.index.has_duplicates or not raw_closes.index.is_monotonic_increasing or
            not isinstance(distributions, pd.Series) or not isinstance(split_ratios, pd.Series) or
            not distributions.index.equals(raw_closes.index) or not split_ratios.index.equals(raw_closes.index)):
        raise ValueError('Exactly aligned ordered action/close series required.')
    data = np.column_stack([raw_closes, distributions, split_ratios]).astype(float)
    if (not np.isfinite(data).all() or (data[:, 0] <= 0).any() or
            (data[:, 1] < 0).any() or (data[:, 2] <= 0).any()):
        raise ValueError('Invalid close/distribution/split input.')
    if data[0, 1] != 0 or data[0, 2] != 1:
        raise ValueError('Action on first observation requires an earlier anchor close.')
    values = [D(100)]
    for i in range(1, len(raw_closes)):
        value = values[-1] * D(split_ratios.iloc[i]) * (D(raw_closes.iloc[i]) + D(distributions.iloc[i])) / D(raw_closes.iloc[i-1])
        if not math.isfinite(float(value)) or value <= 0:
            raise ValueError('Index exceeds positive finite domain.')
        values.append(value)
    return pd.Series([float(v) for v in values], index=raw_closes.index, name='total_return_index')


def monthly_decisions(total_return_index, calendar):
    """10-month SMA sleeves and 10-month top-one strength; next-session decisions.

    Calendar must have separately qualified exchange coverage. Month-end is used
    only when a later calendar session belongs to the next month. No incomplete
    final month is treated as a completed decision close. No execution prices are
    taken from this signal index.
    """
    tri = total_return_index
    if (not isinstance(calendar, pd.DatetimeIndex) or calendar.tz is not None or
            calendar.has_duplicates or not calendar.is_monotonic_increasing or len(calendar) < 2 or
            not calendar.equals(calendar.normalize()) or
            not isinstance(tri, pd.DataFrame) or set(tri) != set(SYMBOLS) or
            not tri.index.equals(calendar)):
        raise ValueError('Exact ordered unique daily calendar and three-symbol coverage required.')
    values = tri.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Positive finite signal marks required; never forward-fill missing marks.')
    # The next session's month is calendar information, not a future price.
    boundaries = np.flatnonzero(calendar[:-1].to_period('M') != calendar[1:].to_period('M'))
    history = []
    decisions = []
    for position in boundaries:
        history.append(tri.iloc[position].reindex(SYMBOLS))
        trend = {symbol: 0. for symbol in SYMBOLS}
        strength = trend.copy()
        ranks = None
        if len(history) >= 10:
            mean = pd.DataFrame(history[-10:]).mean()
            trend = {s: 1/3 if history[-1][s] > mean[s] else 0. for s in SYMBOLS}
        if len(history) >= 11:
            returns = history[-1] / history[-11] - 1
            ranks = {s: float(returns[s]) for s in SYMBOLS}
            winner = min(SYMBOLS, key=lambda s: (-returns[s], s))
            if returns[winner] > 0:
                strength[winner] = 1.
        decisions.append(dict(observed_close=calendar[position].strftime('%Y-%m-%d'),
                              execution_open=calendar[position+1].strftime('%Y-%m-%d'),
                              months_observed=len(history),
                              static_equal={s: 1/3 for s in SYMBOLS},
                              trend_equal=trend, relative_strength=strength,
                              trailing_10_month_returns=ranks))
    return decisions


@dataclass(frozen=True)
class PlannedOrder:
    symbol: str
    delta: int
    expected_fill: Decimal
    commission: Decimal


def plan_rebalance(cash, positions, marks, weights, cost_bps=5, commission=1, reserve=.99):
    """Plan whole-share sells before affordable buys against one USD cash account.

    Inputs are observed cash/positions and simultaneous raw execution marks.
    Receivables are intentionally absent: they cannot fund purchases. This is a
    deterministic order proposal; a native adapter must await actual fills and
    recheck cash/prices before submitting the next order. No persistence or OMS.
    """
    if any(set(mapping) != set(SYMBOLS) for mapping in (positions, marks, weights)):
        raise ValueError('All three instrument identities required; no missing-mark fallback.')
    numbers = [cash, cost_bps, commission, reserve, *marks.values(), *weights.values()]
    if not all(math.isfinite(float(v)) for v in numbers):
        raise ValueError('Finite planner inputs required.')
    if (D(cash) < 0 or not 0 <= D(cost_bps) < 10000 or D(commission) < 0 or
            not 0 < D(reserve) <= 1 or any(D(v) <= 0 for v in marks.values()) or
            any(D(v) < 0 for v in weights.values()) or sum(map(D, weights.values())) > 1):
        raise ValueError('Cash-only weights/cost policy invalid.')
    if any(type(v) is not int or v < 0 for v in positions.values()):
        raise ValueError('Nonnegative whole-share inventories required.')
    available = D(cash)
    held = positions.copy()
    equity = available + sum(D(marks[s]) * held[s] for s in SYMBOLS)
    targets = {s: int((equity * D(reserve) * D(weights[s]) / D(marks[s])).to_integral_value(rounding=ROUND_FLOOR))
               for s in SYMBOLS}
    orders = []
    def filled_price(symbol, buying):
        price = (D(marks[symbol]) * (1 + (1 if buying else -1) * D(cost_bps) / 10000)).quantize(D('.01'), rounding=ROUND_HALF_EVEN)
        if price <= 0:
            raise ValueError('Fill rounds to a nonpositive cent price.')
        return price
    def append(symbol, delta):
        nonlocal available
        price = filled_price(symbol, delta > 0)
        available -= delta * price + D(commission)
        held[symbol] += delta
        if available < 0:
            raise AssertionError('Planner created negative spendable cash.')
        orders.append(PlannedOrder(symbol, delta, price, D(commission)))
    for s in SYMBOLS:
        delta = targets[s] - held[s]
        if delta < 0:
            # A position whose entire proceeds cannot pay its fee is a model
            # failure, not permission to borrow or silently leave a risk-off order.
            if available + (-delta) * filled_price(s, False) < D(commission):
                raise ValueError('Insufficient cash/proceeds to pay liquidation fee.')
            append(s, delta)
    for s in SYMBOLS:
        delta = targets[s] - held[s]
        if delta <= 0:
            continue
        affordable = max(0, int(((available - D(commission)) / filled_price(s, True)).to_integral_value(rounding=ROUND_FLOOR)))
        quantity = min(delta, affordable)
        if quantity:
            append(s, quantity)
    return orders


class DividendReceivables:
    """Small entitlement proposal book; no automatic native cash adjustment.

    A qualified action adapter supplies stable IDs, exact ex/pay dates and
    prior-close eligible inventory. Payment proposals are explicitly acknowledged
    only after the caller observes the cash credit. Unconfirmed/unknown outcomes
    must stop the adapter; this in-memory helper is not crash-safe persistence.
    """
    def __init__(self):
        self.entries = {}
        self.paid = set()

    def accrue(self, action_id, symbol, ex_date, pay_date, per_share, eligible_shares):
        ex = pd.Timestamp(ex_date)
        pay = pd.Timestamp(pay_date)
        if (not isinstance(action_id, str) or not action_id or symbol not in SYMBOLS or
                pd.isna(ex) or pd.isna(pay) or ex != ex.normalize() or pay != pay.normalize() or
                ex.tz is not None or pay.tz is not None or pay < ex or
                not math.isfinite(float(per_share)) or D(per_share) <= 0 or
                type(eligible_shares) is not int or eligible_shares < 0):
            raise ValueError('Verified action dates, positive amount and eligible whole shares required.')
        entry = (symbol, ex, pay, D(per_share) * eligible_shares)
        if action_id in self.entries and self.entries[action_id] != entry:
            raise ValueError('Conflicting duplicate action; preserve and stop.')
        self.entries[action_id] = entry

    @property
    def outstanding(self):
        return sum((item[3] for key, item in self.entries.items() if key not in self.paid), D(0))

    def due(self, date):
        day = pd.Timestamp(date)
        return {key: item[3] for key, item in self.entries.items()
                if key not in self.paid and item[2] <= day}

    def confirm_paid(self, action_id, observed_amount, observed_date):
        if action_id not in self.entries or action_id in self.paid:
            raise ValueError('Unknown/already-credited payment; do not credit twice.')
        if D(observed_amount) != self.entries[action_id][3]:
            raise ValueError('Observed credit does not match entitlement.')
        day = pd.Timestamp(observed_date)
        if pd.isna(day) or day.tz is not None or day != day.normalize() or day < self.entries[action_id][2]:
            raise ValueError('Payment observed before verified payable date.')
        self.paid.add(action_id)
