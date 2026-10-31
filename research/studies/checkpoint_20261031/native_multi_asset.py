"""Native offline ETF account runner with explicit ex-date wealth/pay-date cash.

No source acquisition, broker access or promotion. Historical eligibility/budget
belong to the frozen coordinator; direct use is for synthetic engineering checks.
Reject splits rather than falsely adjusting native positions with artificial fills.
"""
from collections import deque
from decimal import Decimal, ROUND_HALF_EVEN

import numpy as np
import pandas as pd
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig, SimulationModuleConfig
from nautilus_trader.backtest.models import FixedFeeModel
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.config import LoggingConfig, StrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OmsType, AccountType, OrderSide
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy

from research.evaluation.etf_readiness_probe import IDS, VENUE, instrument
from research.studies.checkpoint_20261031.multi_asset import SYMBOLS, plan_rebalance
from research.studies.checkpoint_20261031.us_etf_calendar import clocks

D = lambda value: Decimal(str(value))


class DistributionBook:
    """Exact receivables; per-action half-even cent payment and rounding P&L."""
    def __init__(self, actions):
        self.actions = actions
        self.entitlements = {}
        self.paid = set()
        self.events = []
        self.last_day = None
        ids = set()
        for action in actions:
            if (action['id'] in ids or action['symbol'] not in SYMBOLS or
                    not D(action['amount']).is_finite() or D(action['amount']) <= 0 or
                    pd.Timestamp(action['pay_date']) < pd.Timestamp(action['ex_date'])):
                raise ValueError('Invalid or duplicate qualified action.')
            ids.add(action['id'])

    @property
    def outstanding(self):
        return sum((item['amount'] for key, item in self.entitlements.items() if key not in self.paid), D(0))

    def day(self, date, eligible_positions, credit):
        if date == self.last_day:
            return
        if self.last_day is not None and date < self.last_day:
            raise ValueError('Action lifecycle cannot move backwards.')
        self.last_day = date
        for action in self.actions:
            if action['ex_date'] != date:
                continue
            shares = eligible_positions[action['symbol']]
            amount = shares * D(action['amount'])
            self.entitlements[action['id']] = dict(amount=amount, pay_date=action['pay_date'])
            self.events.append(dict(kind='entitlement', date=date, id=action['id'],
                                    eligible_shares=shares, amount=str(amount)))
        for key, item in self.entitlements.items():
            if key in self.paid or item['pay_date'] > date:
                continue
            rounded = item['amount'].quantize(D('.01'), rounding=ROUND_HALF_EVEN)
            if rounded:
                credit(rounded)
            self.paid.add(key)
            self.events.append(dict(kind='payment', date=date, id=key, amount=str(item['amount']),
                                    cash_credit=str(rounded), rounding_pnl=str(rounded-item['amount'])))


class NativeDistributions(SimulationModule):
    def __init__(self, actions):
        super().__init__(SimulationModuleConfig())
        self.book = DistributionBook(actions)

    def pre_process(self, data):
        date = pd.Timestamp(data.ts_event, tz='UTC').tz_convert('America/New_York').strftime('%Y-%m-%d')
        if date == self.book.last_day:
            return
        positions = {s: sum(int(p.quantity.as_double()) for p in self.exchange.cache.positions_open(instrument_id=IDS[s])) for s in SYMBOLS}
        def credit(amount):
            before = self.exchange.get_account().balance_total(USD).as_decimal()
            self.exchange.adjust_account(Money(float(amount), USD))
            after = self.exchange.get_account().balance_total(USD).as_decimal()
            if after-before != amount:
                raise AssertionError('Native payment cash adjustment mismatch.')
        self.book.day(date, positions, credit)

    def process(self, ts_now):
        pass

    def log_diagnostics(self, logger):
        pass

    def reset(self):
        self.book = DistributionBook(self.book.actions)


class PortfolioReplay(Strategy):
    def __init__(self, frames, targets, cost_bps, module, triggers):
        super().__init__(StrategyConfig())
        self.frames, self.targets, self.cost_bps = frames, targets, cost_bps
        self.module, self.triggers = module, triggers
        self.pending = deque()
        self.active = None
        self.rows, self.trades, self.errors = [], [], []
        self.date = None

    def on_start(self):
        for iid in IDS.values():
            self.subscribe_quote_ticks(iid)

    def positions(self):
        return {s: int(self.portfolio.net_position(IDS[s])) for s in SYMBOLS}

    def cash(self):
        return self.cache.account_for_venue(VENUE).balance_total(USD).as_decimal()

    def on_quote_tick(self, tick):
        if tick.instrument_id != IDS['GLD']:
            return
        date, phase = self.triggers[tick.ts_event]
        self.date = date
        if self.active is not None or self.pending or self.errors:
            raise AssertionError('Unresolved order before next account phase.')
        if phase == 'open':
            if date not in self.targets:
                return
            marks = {s: float(self.frames[s].loc[date, 'open']) for s in SYMBOLS}
            self.pending.extend(plan_rebalance(self.cash(), self.positions(), marks,
                                               self.targets[date], cost_bps=self.cost_bps))
            self.dispatch()
        else:
            positions = self.positions()
            value = sum(positions[s]*D(self.frames[s].loc[date, 'close']) for s in SYMBOLS)
            cash, receivable = self.cash(), self.module.book.outstanding
            equity = cash+value+receivable
            self.rows.append(dict(date=date, cash=float(cash), receivable=float(receivable),
                                  position_value=float(value), equity_usd=float(equity),
                                  exposure=float(value/equity), **{s: positions[s] for s in SYMBOLS}))

    def dispatch(self):
        if not self.pending:
            return
        order = self.pending.popleft()
        if order.delta > 0 and self.cash() < order.delta*order.expected_fill+order.commission:
            raise AssertionError('Observed native cash cannot fund planned purchase.')
        self.active = order
        self.submit_order(self.order_factory.market(IDS[order.symbol],
            OrderSide.BUY if order.delta > 0 else OrderSide.SELL, Quantity.from_int(abs(order.delta))))

    def on_order_filled(self, event):
        expected = self.active
        if (expected is None or event.instrument_id != IDS[expected.symbol] or
                int(event.last_qty.as_double()) != abs(expected.delta) or
                event.last_px.as_decimal() != expected.expected_fill or
                event.commission.as_decimal() != expected.commission):
            self.errors.append('Partial/unexpected fill or fee; no automatic continuation.')
            raise AssertionError(self.errors[-1])
        self.trades.append(dict(date=self.date, symbol=expected.symbol, delta=expected.delta,
                                fill_price=str(event.last_px.as_decimal()), commission=str(event.commission.as_decimal())))
        self.active = None
        self.dispatch()

    def on_order_denied(self, event):
        self.errors.append(str(event))

    def on_order_rejected(self, event):
        self.errors.append(str(event))


def run_native(frames, targets, actions, *, capital=300000, cost_bps=5, splits=()):
    if splits:
        raise ValueError('Native split handling is not configured; reject before simulation.')
    if set(frames) != set(SYMBOLS) or capital <= 0 or not 0 <= cost_bps <= 25:
        raise ValueError('Unsupported research account/universe/cost.')
    dates = frames['SPY'].index
    if len(dates) == 0 or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('Unique ordered evaluation coverage required.')
    for frame in frames.values():
        if not frame.index.equals(dates) or not np.isfinite(frame[['open','close']].to_numpy(float)).all() or (frame[['open','close']]<=0).any().any():
            raise ValueError('Missing or invalid execution marks.')
    if not set(targets) <= set(dates):
        raise ValueError('Target outside evaluation coverage.')
    ticks, triggers = [], {}
    for date in dates:
        opening, closing = clocks(date)
        for phase, stamp in (('open', opening.value), ('close', closing.value)):
            for offset, symbol in enumerate(('SPY', 'IEF', 'GLD')):
                mark = D(frames[symbol].loc[date, phase])
                bid = (mark*(1-D(cost_bps)/10000)).quantize(D('.01'), rounding=ROUND_HALF_EVEN)
                ask = (mark*(1+D(cost_bps)/10000)).quantize(D('.01'), rounding=ROUND_HALF_EVEN)
                if bid <= 0:
                    raise ValueError('Nonpositive modeled bid.')
                ticks.append(QuoteTick(IDS[symbol], Price.from_str(str(bid)), Price.from_str(str(ask)),
                                      Quantity.from_int(10000000), Quantity.from_int(10000000), stamp+offset, stamp+offset))
            triggers[stamp+2] = (date, phase)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    module = NativeDistributions(actions)
    strategy = PortfolioReplay(frames, targets, cost_bps, module, triggers)
    engine.add_venue(VENUE, OmsType.NETTING, AccountType.CASH, [Money(capital, USD)],
                     base_currency=USD, modules=[module], fee_model=FixedFeeModel(Money(1, USD)),
                     bar_execution=False, allow_cash_borrowing=False)
    for symbol in IDS:
        engine.add_instrument(instrument(symbol))
    engine.add_data(ticks)
    engine.add_strategy(strategy)
    try:
        engine.run()
        if strategy.errors or strategy.active or strategy.pending or len(strategy.rows) != len(dates):
            raise ValueError('Incomplete/failed native account path: '+str(strategy.errors))
        return (pd.DataFrame(strategy.rows).set_index('date'), pd.DataFrame(strategy.trades), module.book.events)
    finally:
        engine.dispose()
