"""Independent Decimal replay of recorded trades, costs and daily account values."""
from decimal import Decimal, ROUND_HALF_EVEN
import math
import numpy as np

D = lambda v: Decimal(str(v))


def reconcile(frame, dividends, curve, trades, mode, exposure, model):
    if frame.empty or frame.index.has_duplicates or curve.index.has_duplicates or not frame.index.equals(curve.index):
        raise AssertionError('Audit requires exact unique frame/ledger coverage.')
    keys = ['cash','shares','equity_usd','financing_usd','dividend_usd']
    if not np.isfinite(curve[keys].to_numpy(dtype=float)).all():
        raise AssertionError('Nonfinite accounting evidence.')
    if not trades.empty and (not set(trades.date).issubset(set(frame.index)) or
                            not np.isfinite(trades[['delta','fill_price','mark','cash_after','shares_after']].to_numpy(dtype=float)).all() or
                            not trades.delta.eq(trades.delta.astype(int)).all()):
        raise AssertionError('Invalid trade evidence or coverage.')
    cash, held, halted = D(model.capital), 0, False
    prev = None
    previous_equity = D(model.capital)
    maximum = 0.
    by_date = {date: group.to_dict('records') for date, group in trades.groupby('date')} if not trades.empty else {}
    for date, prices in frame.iterrows():
        from datetime import date as Date
        now = Date.fromisoformat(str(date))
        days = (now - prev).days if prev else 1
        interest = max(-cash, D(0)) * D(model.annual_rate) * days / 360
        dividend = held * D(dividends.get(str(date), 0))
        cash += dividend - interest
        records = by_date.get(str(date), [])
        observed = curve.loc[date]
        def price(mark, delta):
            return (D(mark) * (1 + (1 if delta > 0 else -1) * D(model.cost_bps) / 10000)).quantize(D('.01'), rounding=ROUND_HALF_EVEN)
        expected = []
        def apply(n, mark, reason):
            nonlocal cash, held
            delta = n - held
            if delta:
                filled = price(mark, delta)
                cash -= delta * filled + D(model.commission)
                held = n
                expected.append((delta, float(filled), reason, float(mark), held, float(cash)))
        def margin(mark, stage):
            nonlocal halted
            if held and (cash + held * D(mark) < D(model.maintenance) * held * D(mark) or cash + held * D(mark) <= 0):
                apply(0, mark, 'forced_' + stage)
                halted = True
        overnight=getattr(prices,'execution_schedule','open')=='overnight'
        margin(prices.open, 'open')
        if not halted:
            if getattr(prices,'rebalance_policy','daily') == 'entry_only' and prev is not None:
                n = held
            elif (mode == 'buy_hold' or bool(prices.want_long)) and not overnight:
                equity = cash + held * D(prices.open)
                effective = D(exposure) * D(getattr(prices,'allocation_factor',1.))
                if hasattr(prices,'cppi_floor_fraction'):
                    cushion = D(prices.cppi_multiplier) * max(previous_equity-D(prices.cppi_floor_fraction)*D(model.capital),D(0)) / previous_equity if previous_equity>0 else D(0)
                    effective = min(effective,cushion)
                alpha = effective * D(model.allocation)
                n = max(0, math.floor(alpha * equity / D(prices.open)))
                # Independent descending feasibility search, not the simulator's binary search.
                while n:
                    delta = n - held
                    cost = delta * (price(prices.open, delta) - D(prices.open)) + D(model.commission) if delta else D(0)
                    if n * D(prices.open) <= alpha * (equity - cost):
                        break
                    n -= 1
            else:
                n = 0
            delta = n - held
            fee = delta * (price(prices.open, delta) - D(prices.open)) + D(model.commission) if delta else D(0)
            if delta <= 0 or cash + held * D(prices.open) - fee >= D(model.initial_margin) * n * D(prices.open):
                apply(n, prices.open, 'overnight_exit' if overnight else 'rebalance')
        for stage, mark in [('post_trade',prices.open),('low',prices.low)]:
            margin(mark, stage)
        if overnight and not halted and (mode=='buy_hold' or bool(prices.want_long)):
            equity=cash+held*D(prices.close)
            alpha=D(exposure)*D(model.allocation)
            n=max(0,math.floor(alpha*equity/D(prices.close)))
            while n:
                delta=n-held
                fee=delta*(price(prices.close,delta)-D(prices.close))+D(model.commission) if delta else D(0)
                if n*D(prices.close)<=alpha*(equity-fee):break
                n-=1
            delta=n-held
            fee=delta*(price(prices.close,delta)-D(prices.close))+D(model.commission) if delta else D(0)
            if delta<=0 or equity-fee>=D(model.initial_margin)*n*D(prices.close):
                apply(n,prices.close,'overnight_entry')
        margin(prices.close,'close')
        actual = [(int(r['delta']),float(r['fill_price']),r['reason'],float(r['mark']),int(r['shares_after']),float(r['cash_after'])) for r in records]
        if len(actual) != len(expected) or any(a[:5] != e[:5] or abs(a[5]-e[5]) > .01 for a,e in zip(actual,expected)):
            raise AssertionError(f'Trade audit mismatch {date}: {actual} != {expected}')
        for key, value in [('cash',cash),('equity_usd',cash + held * D(prices.close)),('financing_usd',interest),('dividend_usd',dividend)]:
            difference = abs(float(value) - float(observed[key]))
            maximum = max(maximum, difference)
            if difference > .01:
                raise AssertionError(f'Ledger mismatch {date} {key}: {difference}')
        assert held == observed.shares and halted == bool(observed.halted)
        prev = now
        previous_equity = cash + held * D(prices.close)
    return {'passed':True,'sessions':len(curve),'fills':len(trades),'maximum_difference_usd':maximum}
