"""New bounded synthetic native seam proof. Never uses historical market prices."""
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

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

from research.etf_readiness_probe import IDS, VENUE, instrument, cash
from research.multi_asset import SYMBOLS, DividendReceivables, plan_rebalance

STATE = Path('.local/multi-asset-unlock-v1/state.json')
MARKS = dict(SPY=100, IEF=50, GLD=25)
DATES = ('2020-01-02', '2020-01-03', '2020-01-06')


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


class ReceivableFixture(SimulationModule):
    def __init__(self):
        super().__init__(SimulationModuleConfig())
        self.book = DividendReceivables()
        self.days = set()
        self.records = []

    def pre_process(self, data):
        day = pd.Timestamp(data.ts_event, tz='UTC').strftime('%Y-%m-%d')
        if day in self.days:
            return
        self.days.add(day)
        account = self.exchange.get_account()
        if day == DATES[1]:
            eligible = sum(int(p.quantity.as_double()) for p in self.exchange.cache.positions_open(instrument_id=IDS['IEF']))
            before = cash(account)
            self.book.accrue('fixture-ief', 'IEF', day, DATES[2], 2, eligible)
            self.records.append(dict(kind='ex', shares=eligible, cash_before=before,
                                     cash_after=cash(account), receivable=str(self.book.outstanding)))
        for key, amount in self.book.due(day).items():
            before = cash(account)
            self.exchange.adjust_account(Money(float(amount), USD))
            after = cash(account)
            self.book.confirm_paid(key, Decimal(str(after))-Decimal(str(before)), day)
            self.records.append(dict(kind='pay', cash_before=before, cash_after=after,
                                     amount=str(amount), receivable=str(self.book.outstanding)))

    def process(self, ts_now):
        pass

    def log_diagnostics(self, logger):
        pass

    def reset(self):
        self.book = DividendReceivables()
        self.days.clear()
        self.records.clear()


class AllocatorFixture(Strategy):
    def __init__(self, module):
        super().__init__(StrategyConfig())
        self.module = module
        self.pending = deque()
        self.active = None
        self.fills = []
        self.rows = []
        self.failures = []

    def on_start(self):
        for iid in IDS.values():
            self.subscribe_quote_ticks(iid)

    def on_quote_tick(self, tick):
        if tick.instrument_id != IDS['GLD']:
            return
        day = pd.Timestamp(tick.ts_event, tz='UTC').strftime('%Y-%m-%d')
        account = self.cache.account_for_venue(VENUE)
        positions = {s: int(self.portfolio.net_position(IDS[s])) for s in SYMBOLS}
        self.rows.append(dict(day=day, cash=cash(account), shares=positions,
                              receivable=str(self.module.book.outstanding)))
        if self.active is not None or self.pending:
            raise AssertionError('Unconfirmed previous order; stop instead of duplicate submission.')
        if day == DATES[0]:
            weights = {s: 1/3 for s in SYMBOLS}
        elif day == DATES[1]:
            weights = dict(SPY=0, IEF=0, GLD=1)
        else:
            return
        self.pending.extend(plan_rebalance(cash(account), positions, MARKS, weights))
        self.dispatch()

    def dispatch(self):
        if not self.pending or self.failures:
            return
        order = self.pending.popleft()
        self.active = order
        if order.delta > 0:
            observed_cash = Decimal(str(cash(self.cache.account_for_venue(VENUE))))
            if observed_cash < order.delta * order.expected_fill + order.commission:
                raise AssertionError('Actual native cash cannot fund next planned buy.')
        self.submit_order(self.order_factory.market(IDS[order.symbol],
            OrderSide.BUY if order.delta > 0 else OrderSide.SELL, Quantity.from_int(abs(order.delta))))

    def on_order_filled(self, event):
        expected = self.active
        if (expected is None or event.instrument_id != IDS[expected.symbol] or
                int(event.last_qty.as_double()) != abs(expected.delta) or
                event.last_px.as_decimal() != expected.expected_fill):
            raise AssertionError('Observed native fill differs from the fixture plan.')
        self.fills.append(dict(symbol=expected.symbol, delta=expected.delta,
                               price=str(event.last_px.as_decimal()),
                               commission=str(event.commission.as_decimal())))
        self.active = None
        self.dispatch()  # only after confirmed fill; native cash is checked above

    def on_order_rejected(self, event):
        self.failures.append(str(event))

    def on_order_denied(self, event):
        self.failures.append(str(event))


def run(out):
    module = ReceivableFixture()
    strategy = AllocatorFixture(module)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    engine.add_venue(VENUE, OmsType.NETTING, AccountType.CASH, [Money(1000, USD)],
                     base_currency=USD, modules=[module], fee_model=FixedFeeModel(Money(1, USD)),
                     bar_execution=False, allow_cash_borrowing=False)
    for symbol in IDS:
        engine.add_instrument(instrument(symbol))
    ticks = []
    for day in DATES:
        time = pd.Timestamp(day+'T14:30:00Z').value
        for offset, symbol in enumerate(('SPY', 'IEF', 'GLD')):
            bid = (Decimal(MARKS[symbol])*Decimal('.9995')).quantize(Decimal('.01'))
            ask = (Decimal(MARKS[symbol])*Decimal('1.0005')).quantize(Decimal('.01'))
            ticks.append(QuoteTick(IDS[symbol], Price.from_str(str(bid)), Price.from_str(str(ask)),
                                  Quantity.from_int(100000), Quantity.from_int(100000), time+offset, time+offset))
    engine.add_data(ticks)
    engine.add_strategy(strategy)
    try:
        engine.run()
        write(out/'observations.json', strategy.rows)
        write(out/'fills.json', strategy.fills)
        write(out/'payments.json', module.records)
        write(out/'failures.json', strategy.failures)
        assert not strategy.failures and strategy.active is None and not strategy.pending
        assert len(strategy.fills) == 6
        # Independent scalar Decimal replay: recorded actual native fills, no planner calls.
        balance = Decimal(1000)
        holdings = {s: 0 for s in SYMBOLS}
        for fill in strategy.fills:
            balance -= fill['delta']*Decimal(fill['price']) + Decimal(fill['commission'])
            holdings[fill['symbol']] += fill['delta']
            assert balance >= 0 and all(q >= 0 for q in holdings.values())
        payment = next(row for row in module.records if row['kind']=='pay')
        balance += Decimal(payment['amount'])
        final = strategy.rows[-1]
        assert balance == Decimal(str(final['cash'])) and holdings == final['shares']
        ex = module.records[0]
        assert ex['shares'] == 6 and ex['cash_before'] == ex['cash_after'] and ex['receivable'] == '12'
        assert payment['amount'] == '12' and final['receivable'] == '0'
        assert [(fill['symbol'], fill['delta']) for fill in strategy.fills[3:]] == [('IEF', -6), ('SPY', -3), ('GLD', 26)]
        result = dict(status='synthetic_native_allocator_seam_passed', synthetic_only=True,
                      historical_financial_paths=0, native_fills=6, commission_usd=6,
                      final_cash=str(balance), final_positions=holdings,
                      decimal_replay_passed=True, sell_fill_ack_before_buys=True,
                      ex_date_receivable_not_spendable=True, payment_credited_once=True,
                      split_handler='not implemented or retested; earlier negative evidence preserved',
                      limitations=['Fixed simultaneous synthetic quotes and immediate complete fills only',
                                   'No historical eligibility, partial-fill, restart or broker parity proof',
                                   'Project-side in-memory receivable fixture; no native receivable service'])
        write(out/'proof.json', result)
    finally:
        engine.dispose()


def main():
    state = json.loads(STATE.read_text())
    if len(state['native_synthetic_probes']) >= state['native_synthetic_probe_limit']:
        raise ValueError('New native probe quota exhausted.')
    age = datetime.now(timezone.utc)-datetime.fromisoformat(state['started_utc'])
    if age.total_seconds() >= 3600:
        raise ValueError('Goal deadline exhausted.')
    out = STATE.parent / f'native-{len(state["native_synthetic_probes"])+1}'
    out.mkdir(exist_ok=False)
    sources = ('research/multi_asset.py', 'research/multi_asset_native_probe.py',
               'research/etf_readiness_probe.py', 'requirements.txt', 'requirements.lock.txt')
    code_hashes = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in sources}
    for name in sources:
        (out / ('source-' + name.replace('/', '_'))).write_bytes(Path(name).read_bytes())
    attempt = dict(output=str(out), status='reserved', source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   code_hashes=code_hashes, started_utc=datetime.now(timezone.utc).isoformat())
    state['native_synthetic_probes'].append(attempt)
    write(STATE, state)
    try:
        run(out)
        attempt['status'] = 'completed'
    except Exception as error:
        attempt.update(status='failed', error=repr(error))
        write(out/'failure.json', attempt)
        raise
    finally:
        write(STATE, state)
        write(out/'manifest.json', dict(artifact_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in out.iterdir() if p.is_file() and p.name != 'manifest.json'}))
        print(str(out))


if __name__ == '__main__':
    main()
