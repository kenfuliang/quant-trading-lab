"""NautilusTrader confirmation engine over ``MarketData`` (raw, unadjusted prices).

Reproduces the per-session contract documented in ``screening_engine`` with an
independent accounting: cash comes from the simulated NautilusTrader cash account
and quantities from its portfolio, not from screening arithmetic.

Event layout per session d (America/New_York):

- 09:28 / 09:29, split instruments only: zero-spread quotes at the previous close and
  at ``round(prev_close / ratio, 2)``. A held quantity q is sold at 09:28 and q x ratio
  bought at 09:29; both orders carry the tag ``split`` and are excluded from ``fills``.
  Each split order's commission is credited with ``adjust_account`` *before* it is
  submitted. Before the buy, the rounding residual
  ``q * prev_close - q * ratio * round(prev_close / ratio, 2)`` is cancelled with
  ``adjust_account`` (in exact cents), so the split moves no cash net, as in the
  screening engine, and the cash account never dips below zero.
  Pending targets for the instrument are scaled by the ratio.
- 09:30: quote per instrument (bp from ``cost_bps(data, name, i - 1, config)``, the tier at the
  decision session) with bid ``execution_price(open, "SELL")`` and ask
  ``execution_price(open, "BUY")``. Once every instrument's quote has arrived, the
  orders from the decision at close d-1 are submitted: sells first; after all sells
  fill, buys in instrument order, each checked against the account cash with the known
  ask (overspend raises ``EngineError`` before submission).
- 16:00: daily bar per instrument. Once every bar has arrived, the close is marked
  (equity = account cash + sum(quantity x close)) and ``target_fn`` is called with
  ``history_view(data, i)``, the same view the screening engine passes.

Dividends: a ``SimulationModule`` records holdings at the first event of the ex-date
(the holding at the previous close) and credits ``round(per_share * shares, 2)`` with
``adjust_account`` at the first event of the pay date.

``config`` is checked by ``engine_contract.check_config`` (shared with the screening
engine). A positive ``commission_usd`` uses NautilusTrader's ``FixedFeeModel``, which
rejects zero; a zero commission omits the fee model, so the venue's default
maker/taker model applies with the instruments' maker and taker fees set to 0.
Targets pass ``engine_contract.checked_targets`` and buys ``engine_contract.check_buy``.

Exceptions raised inside strategy callbacks are re-raised unchanged after the run.
Denied/rejected orders and a run that stops early (NautilusTrader stops the backtest
on an ``AccountError``, which bypassed logging would hide) raise ``EngineError`` naming
the cause, the unfilled orders and the account balance.

Synthetic quotes implement the modelled cost; they are not historical quotes.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from nautilus_trader.backtest.config import BacktestEngineConfig, SimulationModuleConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import FixedFeeModel
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.config import LoggingConfig, StrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType, QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy

from research.evaluation.engine_contract import (
    EngineError,
    EngineResult,
    build_result,
    check_buy,
    check_config,
    checked_targets,
    mark,
)
from research.evaluation.market_model import (
    MarketConfig,
    MarketData,
    TargetFn,
    cost_table,
    execution_price,
    history_view,
    validate,
)

VENUE = Venue("SIM")
TZ = "America/New_York"
SPLIT_TAG = "split"
QUOTE_SIZE = 1_000_000_000
SPLIT_SELL, SPLIT_BUY, OPEN, CLOSE = "split_sell", "split_buy", "open", "close"
_TIMES = {SPLIT_SELL: "09:28", SPLIT_BUY: "09:29", OPEN: "09:30", CLOSE: "16:00"}


def _iid(name: str) -> InstrumentId:
    return InstrumentId(Symbol(name), VENUE)


def _bar_type(name: str) -> BarType:
    return BarType.from_str(f"{name}.SIM-1-DAY-LAST-EXTERNAL")


def _price(value: float) -> Price:
    return Price.from_str(f"{value:.2f}")


def _ts(day: str, kind: str) -> int:
    return pd.Timestamp(f"{day} {_TIMES[kind]}", tz=TZ).value


@dataclass(frozen=True)
class _SplitPlan:
    instrument: str
    ratio: int
    prev_close: float
    new_price: float


def _split_plans(data: MarketData) -> dict[str, list[_SplitPlan]]:
    index = {day: k for k, day in enumerate(data.sessions)}
    plans: dict[str, list[_SplitPlan]] = {}
    for split in data.splits:
        i = index[split.effective_date]
        frame = data.bars[split.instrument]
        prev_close = float(frame["close"].iloc[i - 1]) if i > 0 else float(frame["open"].iloc[i])
        plan = _SplitPlan(split.instrument, split.ratio, prev_close, round(prev_close / split.ratio, 2))
        plans.setdefault(split.effective_date, []).append(plan)
    return plans


def _events(data: MarketData, names: list[str], plans: dict[str, list[_SplitPlan]], config: MarketConfig):
    bps = cost_table(data, config)  # bps[n][i - 1]: tier at the decision session i - 1, for the quote at i
    size = Quantity.from_int(QUOTE_SIZE)
    events, ts_info = [], {}
    columns = {n: {c: data.bars[n][c].to_numpy(dtype=float) for c in ("open", "high", "low", "close", "volume")}
               for n in names}
    for i, day in enumerate(data.sessions):
        for plan in plans.get(day, []):
            for kind, px in ((SPLIT_SELL, plan.prev_close), (SPLIT_BUY, plan.new_price)):
                ts = _ts(day, kind)
                ts_info[ts] = (day, kind)
                events.append(QuoteTick(_iid(plan.instrument), _price(px), _price(px), size, size, ts, ts))
        opened, closed = _ts(day, OPEN), _ts(day, CLOSE)
        ts_info[opened], ts_info[closed] = (day, OPEN), (day, CLOSE)
        for name in names:
            col = columns[name]
            open_px = float(col["open"][i])
            events.append(QuoteTick(
                _iid(name),
                _price(execution_price(open_px, "SELL", float(bps[name][max(i - 1, 0)]))),
                _price(execution_price(open_px, "BUY", float(bps[name][max(i - 1, 0)]))),
                size, size, opened, opened,
            ))
            events.append(Bar(
                _bar_type(name), _price(open_px), _price(float(col["high"][i])), _price(float(col["low"][i])),
                _price(float(col["close"][i])), Quantity.from_int(int(col["volume"][i])), closed, closed,
            ))
    return events, ts_info


def _held(cache, name: str) -> int:
    return int(sum(p.signed_qty for p in cache.positions_open(instrument_id=_iid(name))))


class _DividendModule(SimulationModule):
    """Records ex-date entitlements and credits cash on the pay date."""

    def __init__(self, data: MarketData, ts_info: dict[int, tuple[str, str]]):
        super().__init__(SimulationModuleConfig())
        self.dividends = data.dividends
        self.exes_on: dict[str, list[int]] = {}   # ex date -> dividend indexes, ascending
        self.pays_on: dict[str, list[int]] = {}   # pay date -> dividend indexes, ascending
        for k, div in enumerate(data.dividends):
            self.exes_on.setdefault(div.ex_date, []).append(k)
            self.pays_on.setdefault(div.pay_date, []).append(k)
        self.ts_info = ts_info
        self.last_day = None
        self.entitled: dict[int, int] = {}
        self.credits: list[tuple[str, str, int, float]] = []

    def pre_process(self, data):
        day = self.ts_info[data.ts_init][0]
        if day == self.last_day:
            return
        self.last_day = day
        for k in self.exes_on.get(day, ()):
            self.entitled[k] = _held(self.exchange.cache, self.dividends[k].instrument)
        for k in self.pays_on.get(day, ()):
            div = self.dividends[k]
            shares = self.entitled.get(k, 0)
            if shares:
                credit = Money(round(div.per_share * shares, 2), USD)
                self.exchange.adjust_account(credit)
                self.credits.append((day, div.instrument, shares, credit.as_double()))

    def process(self, ts_now):
        pass

    def log_diagnostics(self, logger):
        pass

    def reset(self):
        self.last_day = None
        self.entitled.clear()
        self.credits.clear()


class _ScreenStrategy(Strategy):
    def __init__(self, data: MarketData, target_fn: TargetFn, config: MarketConfig,
                 plans: dict[str, list[_SplitPlan]], ts_info: dict[int, tuple[str, str]], refund):
        super().__init__(StrategyConfig(strategy_id="NativeScreen-001"))
        self.data = data
        self.target_fn = target_fn
        self.market = config
        self.names = sorted(data.bars)
        self.by_iid = {_iid(n): n for n in self.names}
        self.sessions = list(data.sessions)
        self.session_index = {day: k for k, day in enumerate(self.sessions)}
        self.plans = plans
        self.ts_info = ts_info
        self.refund = refund
        self.error: BaseException | None = None
        self.pending: dict[str, int] | None = None
        self.split_qty: dict[str, int] = {}
        self.open_count: dict[str, int] = {}
        self.closes: dict[str, dict[str, float]] = {}
        self.queued_buys: list[tuple[str, int]] = []
        self.open_sells: set = set()
        self.sequence: dict[str, int] = {}
        self.marks: list[dict] = []
        self.signals: list[tuple[str, str, str, float]] = []

    # ---------------------------------------------------------------- helpers
    def _guard(self, fn, *args):
        if self.error is not None:
            return
        try:
            fn(*args)
        except Exception as exc:  # surfaced after the run; NautilusTrader must not swallow it
            self.error = exc

    def _cash(self) -> float:
        return self.cache.account_for_venue(VENUE).balance_total(USD).as_double()

    def _qty(self, name: str) -> int:
        return _held(self.cache, name)

    def _submit(self, name: str, side: OrderSide, quantity: int, tags=None):
        order = self.order_factory.market(_iid(name), side, Quantity.from_int(quantity), tags=tags)
        self.sequence[order.client_order_id.value] = len(self.sequence)
        self.submit_order(order)
        return order

    def _submit_split(self, name: str, side: OrderSide, quantity: int):
        # Credit the expected commission first so the cash account never goes negative.
        if self.market.commission_usd > 0:
            self.refund(Money(self.market.commission_usd, USD))
        self._submit(name, side, quantity, tags=[SPLIT_TAG])

    # ------------------------------------------------------------- callbacks
    def on_start(self):
        for name in self.names:
            self.subscribe_quote_ticks(_iid(name))
            self.subscribe_bars(_bar_type(name))

    def on_quote_tick(self, tick):
        self._guard(self._on_quote, tick)

    def on_bar(self, bar):
        self._guard(self._on_bar, bar)

    def on_order_filled(self, event):
        self._guard(self._on_filled, event)

    def on_order_denied(self, event):
        self._guard(self._fail_order, event)

    def on_order_rejected(self, event):
        self._guard(self._fail_order, event)

    # ----------------------------------------------------------------- logic
    def _fail_order(self, event):
        raise EngineError(f"order {event.client_order_id} not accepted: {event.reason}")

    def _on_quote(self, tick):
        day, kind = self.ts_info[tick.ts_event]
        name = self.by_iid[tick.instrument_id]
        if kind == SPLIT_SELL:
            plan = next(p for p in self.plans[day] if p.instrument == name)
            if self.pending is not None and name in self.pending:
                self.pending[name] = self.pending[name] * plan.ratio
            q = self._qty(name)
            self.split_qty[name] = q
            if q > 0:
                self._submit_split(name, OrderSide.SELL, q)
        elif kind == SPLIT_BUY:
            plan = next(p for p in self.plans[day] if p.instrument == name)
            q = self.split_qty.pop(name, 0)
            if q > 0:
                # Cancel the sell/rebuy rounding residual so the split moves no cash.
                residual_cents = q * round(plan.prev_close * 100) - q * plan.ratio * round(plan.new_price * 100)
                if residual_cents:
                    self.refund(Money(-residual_cents / 100, USD))
                self._submit_split(name, OrderSide.BUY, q * plan.ratio)
        elif kind == OPEN:
            self.open_count[day] = self.open_count.get(day, 0) + 1
            if self.open_count[day] == len(self.names):
                self._trade_open()

    def _trade_open(self):
        if self.pending is None:
            return
        diffs = {n: self.pending.get(n, 0) - self._qty(n) for n in self.names}
        self.queued_buys = [(n, d) for n, d in diffs.items() if d > 0]
        for n, d in diffs.items():
            if d < 0:
                order = self._submit(n, OrderSide.SELL, -d)
                self.open_sells.add(order.client_order_id)
        if not self.open_sells:
            self._submit_buys()

    def _submit_buys(self):
        buys, self.queued_buys = self.queued_buys, []
        cash = self._cash()
        commission = self.market.commission_usd
        day = self.ts_info[self.clock.timestamp_ns()][0]
        for name, q in buys:
            price = self.cache.quote_tick(_iid(name)).ask_price.as_double()
            cash = check_buy(day, name, q, price, cash, commission)
            self._submit(name, OrderSide.BUY, q)

    def _on_filled(self, event):
        order = self.cache.order(event.client_order_id)
        if SPLIT_TAG in (order.tags or []):
            # The commission was credited before submission; it must match what was charged.
            if order.is_closed:
                charged = sum(c.as_double() for c in order.commissions())
                if abs(charged - self.market.commission_usd) > 1e-9:
                    raise EngineError(f"split order {event.client_order_id} charged {charged}, "
                                      f"expected {self.market.commission_usd}")
            return
        if event.client_order_id in self.open_sells and order.is_closed:
            self.open_sells.discard(event.client_order_id)
            if not self.open_sells:
                self._submit_buys()

    def _on_bar(self, bar):
        day = self.ts_info[bar.ts_event][0]
        name = self.by_iid[bar.bar_type.instrument_id]
        self.closes.setdefault(day, {})[name] = bar.close.as_double()
        if len(self.closes[day]) == len(self.names):
            self._mark_and_decide(day)

    def _mark_and_decide(self, day: str):
        if self.open_sells or self.queued_buys or self.split_qty:
            raise EngineError(f"{day}: orders still outstanding at the close")
        qty = {n: self._qty(n) for n in self.names}
        self.marks.append(mark(day, self._cash(), qty, {n: self.closes[day][n] for n in self.names}))
        i = self.session_index[day]
        if i == len(self.sessions) - 1:
            self.pending = None
            return
        decision = self.target_fn(day, history_view(self.data, i), dict(qty), self.marks[-1]["equity"])
        try:
            self.pending = checked_targets(decision, self.names)
        except EngineError as exc:
            raise EngineError(f"{day}: {exc}") from None
        for (n, stage), value in decision.signals.items():
            self.signals.append((day, n, stage, float(value)))


def _early_stop_message(engine: BacktestEngine, strategy: _ScreenStrategy, sessions: int) -> str:
    def describe(o) -> str:
        split = " [split]" if SPLIT_TAG in (o.tags or []) else ""
        return f"{o.client_order_id} {o.side_string()} {o.quantity} {o.instrument_id} {o.status_string()}{split}"

    last = strategy.marks[-1]["date"] if strategy.marks else "none"
    orders = sorted(engine.cache.orders(), key=lambda o: o.ts_init)
    unfilled = [describe(o) for o in orders if o.filled_qty < o.quantity]
    account = engine.cache.account_for_venue(VENUE)
    balance = account.balance_total(USD) if account is not None else None
    return (
        f"NautilusTrader stopped the run early: marked {len(strategy.marks)} of {sessions} sessions "
        f"(last marked {last}); account balance {balance}; last order "
        f"{describe(orders[-1]) if orders else 'none'}; unfilled orders {unfilled or 'none'}. "
        "A cash account stops the backtest on an AccountError, e.g. a fill that would make cash negative."
    )


def _fill_rows(report: pd.DataFrame, data: MarketData, sequence: dict[str, int]) -> list[tuple]:
    if report.empty:
        return []
    index = {day: k for k, day in enumerate(data.sessions)}
    rows = []
    for client_order_id, row in report.iterrows():
        if SPLIT_TAG in (row["tags"] or []):
            continue
        ts = pd.Timestamp(row["ts_last"])
        day = ts.tz_convert(TZ).strftime("%Y-%m-%d")
        name = InstrumentId.from_str(str(row["instrument_id"])).symbol.value
        quantity = int(float(row["filled_qty"]))
        price = float(row["avg_px"])
        commission = sum(Money.from_str(c).as_double() for c in row["commissions"])
        open_px = float(data.bars[name]["open"].iloc[index[day]])
        rows.append((ts.value, sequence[str(client_order_id)],
                     (day, name, str(row["side"]), quantity, price, commission + abs(price - open_px) * quantity)))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [r[2] for r in rows]


def run_native(data: MarketData, target_fn: TargetFn, config: MarketConfig) -> EngineResult:
    validate(data)
    check_config(config)
    names = sorted(data.bars)
    plans = _split_plans(data)
    events, ts_info = _events(data, names, plans, config)

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR", bypass_logging=True)))
    try:
        module = _DividendModule(data, ts_info)
        fee_model = FixedFeeModel(Money(config.commission_usd, USD)) if config.commission_usd > 0 else None
        engine.add_venue(
            VENUE, OmsType.NETTING, AccountType.CASH, [Money(config.initial_cash, USD)],
            base_currency=USD, modules=[module], fee_model=fee_model,
            bar_execution=False, allow_cash_borrowing=False,
        )
        for name in names:
            engine.add_instrument(Equity(_iid(name), Symbol(name), USD, 2, Price.from_str("0.01"),
                                         Quantity.from_int(1), 0, 0, maker_fee=Decimal(0), taker_fee=Decimal(0)))
        engine.add_data(events)
        strategy = _ScreenStrategy(data, target_fn, config, plans, ts_info,
                                   refund=lambda money: module.exchange.adjust_account(money))
        engine.add_strategy(strategy)
        with warnings.catch_warnings():
            # NautilusTrader 1.231 calls the deprecated pandas Timestamp.utcnow internally.
            warnings.filterwarnings("ignore", message="Timestamp.utcnow is deprecated")
            engine.run()
        if strategy.error is not None:
            raise strategy.error
        if len(strategy.marks) != len(data.sessions):
            raise EngineError(_early_stop_message(engine, strategy, len(data.sessions)))
        fills = _fill_rows(engine.trader.generate_order_fills_report(), data, strategy.sequence)
    finally:
        engine.dispose()

    return build_result("nautilus", strategy.marks, fills, strategy.signals, config.initial_cash)
