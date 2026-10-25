"""Offline long-stock margin ledger; contract: research/leverage-model.md."""
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_EVEN
import math

import numpy as np
import pandas as pd

from reporting.annual import calmar, sharpe


@dataclass(frozen=True)
class FinancingModel:
    capital: float = 300000.0
    annual_rate: float = .06
    allocation: float = .99
    initial_margin: float = .50
    maintenance: float = .25
    cost_bps: float = 5.0
    commission: float = 1.0

    def __post_init__(self):
        values = list(asdict(self).values())
        if not all(math.isfinite(x) for x in values) or self.capital <= 0 or self.annual_rate < 0:
            raise ValueError('Invalid financing model.')
        if not (0 < self.allocation <= 1 and 0 < self.maintenance <= self.initial_margin <= 1):
            raise ValueError('Invalid margin/allocation.')
        if not (0 <= self.cost_bps < 10000 and self.commission >= 0):
            raise ValueError('Invalid costs.')


def fill_price(mark, buying, model):
    factor = Decimal(1) + (1 if buying else -1) * Decimal(str(model.cost_bps)) / 10000
    return float((Decimal(str(mark)) * factor).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN))


def target_shares(cash, held, mark, exposure, model):
    equity = cash + held * mark
    if equity <= 0:
        return 0
    alpha = exposure * model.allocation
    low, high = 0, max(0, math.floor(alpha * equity / mark))
    while low < high:
        n = (low + high + 1) // 2
        delta = n - held
        cost = 0 if delta == 0 else delta * (fill_price(mark, delta > 0, model) - mark) + model.commission
        if n * mark <= alpha * (equity - cost):
            low = n
        else:
            high = n - 1
    return low


def simulate(frame, dividends, mode, exposure, model=FinancingModel()):
    """Frame includes a prior-close want_long flag, never a same-day signal."""
    if mode not in ('trend', 'buy_hold') or not math.isfinite(exposure) or not 1 <= exposure <= 2:
        raise ValueError('Unsupported signal/exposure.')
    if frame.empty or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError('Invalid evaluation dates.')
    data = frame[['open', 'low', 'close']].to_numpy(dtype=float)
    if not np.isfinite(data).all() or (data <= 0).any() or (frame.low > frame[['open','close']].min(axis=1)).any():
        raise ValueError('Invalid evaluation prices.')
    if 'allocation_factor' in frame and (not np.isfinite(frame.allocation_factor).all() or not frame.allocation_factor.between(0,1).all()):
        raise ValueError('Allocation factor must be finite and between zero and one.')
    if ('cppi_floor_fraction' in frame) != ('cppi_multiplier' in frame):
        raise ValueError('Both CPPI parameters are required.')
    if 'cppi_floor_fraction' in frame and (not np.isfinite(frame[['cppi_floor_fraction','cppi_multiplier']]).all().all() or not frame.cppi_floor_fraction.between(0,1).all() or (frame.cppi_multiplier<=0).any()):
        raise ValueError('Invalid CPPI policy.')
    if 'execution_schedule' in frame and not frame.execution_schedule.isin(['open','overnight']).all():
        raise ValueError('Unsupported execution schedule.')
    if 'execution_schedule' in frame and (frame.execution_schedule=='overnight').any() and any(k in frame for k in ('allocation_factor','cppi_floor_fraction')):
        raise ValueError('Combined overnight/sizing overlays are outside the defined contract.')
    entry_only = 'rebalance_policy' in frame
    if entry_only and (not frame.rebalance_policy.eq('entry_only').all() or mode != 'buy_hold'
                       or exposure != 1 or any(k in frame for k in ('cppi_floor_fraction','execution_schedule'))
                       or ('allocation_factor' in frame and not frame.allocation_factor.eq(1).all())):
        raise ValueError('Entry-only policy requires unmodified nominal 1x buy/hold.')
    cash, held, halted = model.capital, 0, False
    previous_equity = model.capital
    previous_date = pd.Timestamp(frame.index[0]) - pd.Timedelta(days=1)
    rows, trades = [], []
    for date, row in frame.iterrows():
        now = pd.Timestamp(date)
        days = (now - previous_date).days
        interest = max(-cash, 0) * model.annual_rate * days / 360
        dividend = held * dividends.get(str(now.date()), 0)
        cash += dividend - interest
        day_fees, day_slippage, forced, denied = 0., 0., 0, 0
        max_exposure, min_buffer = 0., 100.
        def trade(quantity, mark, reason):
            nonlocal cash, held, day_fees, day_slippage
            delta = quantity - held
            if not delta:
                return
            price = fill_price(mark, delta > 0, model)
            cash -= delta * price + model.commission
            held = quantity
            day_fees += model.commission
            day_slippage += delta * (price - mark)
            trades.append({'date': str(now.date()), 'delta': delta, 'fill_price': price,
                           'mark': mark, 'reason': reason, 'cash_after': cash, 'shares_after': held})
        def risk(mark, stage):
            nonlocal halted, forced, max_exposure, min_buffer
            value = held * mark
            eq = cash + value
            if eq > 0:
                max_exposure = max(max_exposure, value / eq)
                min_buffer = min(min_buffer, (eq - model.maintenance * value) / eq * 100)
            elif held:
                min_buffer = float('-inf')
            if held and (eq <= 0 or eq < model.maintenance * value):
                trade(0, mark, 'forced_' + stage)
                halted, forced = True, forced + 1
        effective_exposure = exposure * float(getattr(row,'allocation_factor',1.))
        if hasattr(row,'cppi_floor_fraction'):
            cushion_exposure = row.cppi_multiplier * max(previous_equity - row.cppi_floor_fraction*model.capital,0) / previous_equity if previous_equity>0 else 0.
            effective_exposure = min(effective_exposure,cushion_exposure)
        overnight = getattr(row,'execution_schedule','open') == 'overnight'
        risk(row.open, 'open')
        if not halted:
            desired = (mode == 'buy_hold' or bool(row.want_long)) and not overnight
            n = target_shares(cash, held, row.open, effective_exposure, model) if desired else 0
            if entry_only and date != frame.index[0]:
                n = held
            delta = n - held
            cost = 0 if delta == 0 else delta * (fill_price(row.open, delta > 0, model) - row.open) + model.commission
            equity_after = cash + held * row.open - cost
            if delta > 0 and equity_after < model.initial_margin * n * row.open:
                denied = 1
            else:
                trade(n, row.open, 'overnight_exit' if overnight else 'rebalance')
        risk(row.open, 'post_trade')
        risk(row.low, 'low')
        if overnight and not halted and (mode == 'buy_hold' or bool(row.want_long)):
            n = target_shares(cash,held,row.close,effective_exposure,model)
            delta = n-held
            cost = 0 if delta==0 else delta*(fill_price(row.close,delta>0,model)-row.close)+model.commission
            if delta>0 and cash+held*row.close-cost < model.initial_margin*n*row.close:
                denied += 1
            else:
                trade(n,row.close,'overnight_entry')
        risk(row.close, 'close')
        equity = cash + held * row.close
        rows.append({'date': str(now.date()), 'cash': cash, 'shares': held, 'close': row.close,
                     'equity_usd': equity, 'effective_target_leverage': effective_exposure, 'financing_usd': interest, 'dividend_usd': dividend,
                     'commission_usd': day_fees, 'slippage_usd': day_slippage,
                     'max_checked_leverage': max_exposure, 'min_margin_buffer_pct': min_buffer,
                     'forced_liquidations': forced, 'initial_margin_rejections': denied,
                     'halted': halted, 'insolvent': equity <= 0})
        previous_date = now
        previous_equity = equity
    return pd.DataFrame(rows).set_index('date'), pd.DataFrame(trades)


def score_period(values):
    values = np.asarray(values, dtype=float)
    returns = values[1:] / values[:-1] - 1 if (values > 0).all() else None
    dd = float((values / np.maximum.accumulate(values) - 1).min() * 100) if values[0] > 0 else float('nan')
    gain = float((values[-1] / values[0] - 1) * 100) if values[0] > 0 else float('nan')
    return gain, dd, sharpe(returns) if returns is not None else float('nan')


def score_rows(curve, model, label, mode, exposure):
    eq = curve.equity_usd.to_numpy()
    values = np.r_[model.capital, eq]
    total, dd, sr = score_period(values)
    years = (pd.Timestamp(curve.index[-1]) - pd.Timestamp(curve.index[0])).days / 365.25
    cagr = ((eq[-1] / model.capital) ** (1 / years) - 1) * 100 if (values > 0).all() and years > 0 else float('nan')
    def make(period, group, gain, drawdown, ratio, ending):
        return {'period': period, 'strategy': label, 'mode': mode, 'exposure': exposure,
                'return_pct': gain, 'drawdown_pct': drawdown, 'calmar': calmar(gain, drawdown) if np.isfinite(ratio) else float('nan'),
                'sharpe': ratio, 'ending_equity': ending, 'financing_usd': group.financing_usd.sum(),
                'commission_usd': group.commission_usd.sum(), 'slippage_usd': group.slippage_usd.sum(),
                'dividend_usd': group.dividend_usd.sum(), 'max_leverage': group.max_checked_leverage.max(),
                'min_buffer_pct': group.min_margin_buffer_pct.min(), 'liquidations': int(group.forced_liquidations.sum()),
                'status': 'INSOLVENT' if group.insolvent.any() else ('HALTED' if group.halted.any() else 'ACTIVE')}
    rows = [make('Overall', curve, cagr, dd, sr, eq[-1])]
    rows[0]['total_return_pct'] = total
    years_index = pd.to_datetime(curve.index).year
    previous = model.capital
    for year in sorted(set(years_index)):
        group = curve.loc[years_index == year]
        vals = np.r_[previous, group.equity_usd.to_numpy()]
        gain, drawdown, ratio = score_period(vals)
        row = make(str(year), group, gain, drawdown, ratio, vals[-1])
        # Calmar does not require nonzero daily variance, only positive equity and nonzero drawdown.
        row['calmar'] = calmar(gain, drawdown) if (vals > 0).all() else float('nan')
        rows.append(row)
        previous = vals[-1]
    rows[0]['calmar'] = calmar(cagr, dd) if (values > 0).all() else float('nan')
    return rows
