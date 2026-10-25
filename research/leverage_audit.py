"""Independent Decimal replay of recorded trades, costs and daily account values."""
from decimal import Decimal, ROUND_HALF_EVEN
import math

D = lambda v: Decimal(str(v))


def reconcile(frame, dividends, curve, trades, mode, exposure, model):
    cash, held, halted = D(model.capital), 0, False
    prev = None
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
                expected.append((delta, float(filled), reason))
        def margin(mark, stage):
            nonlocal halted
            if held and (cash + held * D(mark) < D(model.maintenance) * held * D(mark) or cash + held * D(mark) <= 0):
                apply(0, mark, 'forced_' + stage)
                halted = True
        margin(prices.open, 'open')
        if not halted:
            if mode == 'buy_hold' or bool(prices.want_long):
                equity = cash + held * D(prices.open)
                alpha = D(exposure) * D(model.allocation)
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
                apply(n, prices.open, 'rebalance')
        for stage, mark in [('post_trade',prices.open),('low',prices.low),('close',prices.close)]:
            margin(mark, stage)
        actual = [(int(r['delta']),float(r['fill_price']),r['reason']) for r in records]
        if actual != expected:
            raise AssertionError(f'Trade audit mismatch {date}: {actual} != {expected}')
        for key, value in [('cash',cash),('equity_usd',cash + held * D(prices.close)),('financing_usd',interest),('dividend_usd',dividend)]:
            difference = abs(float(value) - float(observed[key]))
            maximum = max(maximum, difference)
            if difference > .01:
                raise AssertionError(f'Ledger mismatch {date} {key}: {difference}')
        assert held == observed.shares and halted == bool(observed.halted)
        prev = now
    return {'passed':True,'sessions':len(curve),'fills':len(trades),'maximum_difference_usd':maximum}
