"""Independent Decimal policy/account replay; no native portfolio/planner calls."""
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN
import numpy as np
from research.multi_asset import SYMBOLS

D = lambda value: Decimal(str(value))


def reconcile(frames, targets, actions, curve, trades, events, *, capital=300000, cost_bps=5):
    dates = frames['SPY'].index
    if not curve.index.equals(dates) or not np.isfinite(curve.select_dtypes(include='number').to_numpy()).all():
        raise AssertionError('Nonfinite/incomplete native financial path.')
    by_date = {date: group.to_dict('records') for date, group in trades.groupby('date')} if not trades.empty else {}
    cash, held = D(capital), {s: 0 for s in SYMBOLS}
    entitled, paid = {}, set()
    maximum, total_fills = 0., 0
    expected_events = []
    for date in dates:
        for action in actions:
            if action['ex_date'] == date:
                amount = held[action['symbol']]*D(action['amount'])
                entitled[action['id']] = (amount, action['pay_date'])
                expected_events.append(dict(kind='entitlement', date=date, id=action['id'],
                                            eligible_shares=held[action['symbol']], amount=str(amount)))
        for key, (amount, pay) in entitled.items():
            if key not in paid and pay <= date:
                credit = amount.quantize(D('.01'), rounding=ROUND_HALF_EVEN)
                cash += credit
                paid.add(key)
                expected_events.append(dict(kind='payment', date=date, id=key, amount=str(amount),
                                            cash_credit=str(credit), rounding_pnl=str(credit-amount)))
        expected = []
        if date in targets:
            marks = {s: D(frames[s].loc[date, 'open']) for s in SYMBOLS}
            wealth_spendable = cash+sum(held[s]*marks[s] for s in SYMBOLS)
            desired = {s: int((wealth_spendable*D('.99')*D(targets[date][s])/marks[s]).to_integral_value(rounding=ROUND_FLOOR)) for s in SYMBOLS}
            def fill(s, quantity):
                nonlocal cash
                price = (marks[s]*(1+(1 if quantity > 0 else -1)*D(cost_bps)/10000)).quantize(D('.01'), rounding=ROUND_HALF_EVEN)
                cash -= quantity*price+1
                held[s] += quantity
                expected.append((s, quantity, price, D(1)))
                if cash < 0 or held[s] < 0:
                    raise AssertionError('Independent policy overspent or shorted.')
            for s in SYMBOLS:
                if desired[s] < held[s]:
                    fill(s, desired[s]-held[s])
            for s in SYMBOLS:
                quantity = max(0, desired[s]-held[s])
                price = (marks[s]*(1+D(cost_bps)/10000)).quantize(D('.01'), rounding=ROUND_HALF_EVEN)
                while quantity and quantity*price+1 > cash:
                    quantity -= 1
                if quantity:
                    fill(s, quantity)
        actual = [(r['symbol'], int(r['delta']), D(r['fill_price']), D(r['commission'])) for r in by_date.get(date, [])]
        if actual != expected:
            raise AssertionError('Independent target/trade mismatch '+date+': '+str((actual, expected)))
        total_fills += len(actual)
        receivable = sum((amount for key, (amount, _) in entitled.items() if key not in paid), D(0))
        value = sum(held[s]*D(frames[s].loc[date, 'close']) for s in SYMBOLS)
        for name, amount in (('cash', cash), ('receivable', receivable), ('position_value', value), ('equity_usd', cash+value+receivable)):
            error = abs(D(curve.loc[date, name])-amount)
            maximum = max(maximum, float(error))
            if error > D('.000001'):
                raise AssertionError('Independent cash/NAV mismatch '+date+'/'+name)
        if any(held[s] != int(curve.loc[date, s]) for s in SYMBOLS):
            raise AssertionError('Independent share mismatch.')
    if expected_events != events:
        raise AssertionError('Entitlement/payment/rounding event mismatch.')
    return dict(passed=True, sessions=len(dates), fills=total_fills, maximum_difference_usd=maximum,
                terminal_receivable_usd=str(receivable), native_cash_and_inventory_verified=True,
                target_policy_implementation='Independent descending affordability check; no project planner called')
