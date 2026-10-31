"""Single-session native extension, deliberately not a general Alpaca adapter.

Flat-account start, one SPY position, at most two DAY limits, no restart recovery.
Native reconciliation is disabled for this scoped client; independent broker
checks/journal gates are mandatory. Unsupported report/recovery calls fail closed.
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path

from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import LoggingConfig, TradingNodeConfig
from nautilus_trader.live.config import LiveDataClientConfig, LiveExecClientConfig, LiveExecEngineConfig, LiveRiskEngineConfig
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.live.factories import LiveDataClientFactory, LiveExecClientFactory
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import Bar, QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, OrderType, TimeInForce, LiquiditySide
from nautilus_trader.model.identifiers import AccountId, ClientId, TradeId, VenueOrderId
from nautilus_trader.model.objects import AccountBalance, Money, Price, Quantity
from nautilus_trader.model.currencies import USD

from research.studies.spy.spy_backtest import ComparisonStrategy, ComparisonConfig, INSTRUMENT_ID, BAR_TYPE, VENUE, instrument
from .alpaca import PaperError, MAX_NOTIONAL, validate_order, save


class BoundedSPY(ComparisonStrategy):
    """Reuse original EMA/on_bar, change only bounded sizing and order policy."""
    def __init__(self, context):
        super().__init__(ComparisonConfig(mode="trend", start="2000-01-01", end="2100-01-01", fast=50, slow=200))
        self.context = context

    def on_quote_tick(self, tick):
        ctx = self.context
        if not ctx.armed or ctx.unknown or ctx.pending or not self.slow.initialized:
            return
        desired = self.want_long
        qty = Decimal(str(self.portfolio.net_position(INSTRUMENT_ID)))
        ctx.events.append({"type": "decision", "want_long": desired,
            "fast": self.fast.value, "slow": self.slow.value, "native_position": str(qty)})
        if (desired and qty == 1) or (not desired and qty == 0):
            return
        side = OrderSide.BUY if desired else OrderSide.SELL
        value = tick.ask_price.as_decimal() if desired else tick.bid_price.as_decimal()
        value = (value * (Decimal("1.001") if desired else Decimal("0.999"))).quantize(Decimal("0.01"))
        if not 0 < value <= MAX_NOTIONAL or ctx.submissions >= 2:
            ctx.armed = False
            ctx.events.append({"type": "policy_stop"})
            return
        ctx.pending = True
        self.submit_order(self.order_factory.limit(INSTRUMENT_ID, side,
            Quantity.from_int(1), Price.from_str(str(value)), time_in_force=TimeInForce.DAY))


class Context:
    def __init__(self, api, root, cash="100000", fake=False):
        self.api, self.root, self.cash, self.fake = api, Path(root), cash, fake
        self.root.mkdir(parents=True, exist_ok=True)
        self.armed = self.pending = self.unknown = False
        self.submissions = self.fills = 0
        self.position = Decimal(0)
        self.events, self.journal = [], []
        self.data = self.execution = None
        self.tasks = []


class BoundedData(LiveMarketDataClient):
    def __init__(self, context, **kwargs):
        super().__init__(client_id=ClientId("SIM"), venue=VENUE,
                         instrument_provider=InstrumentProvider(), **kwargs)
        self.context = context
        context.data = self

    async def _connect(self):
        self._handle_data(instrument())

    async def _disconnect(self):
        pass

    async def _subscribe_quote_ticks(self, command):
        if command.instrument_id != INSTRUMENT_ID:
            raise PaperError("Unsupported instrument.")

    async def _subscribe_bars(self, command):
        if command.bar_type != BAR_TYPE:
            raise PaperError("Unsupported bar type.")

    async def _unsubscribe_quote_ticks(self, command):
        pass

    async def _unsubscribe_bars(self, command):
        pass

    def feed(self, data):
        self._handle_data(data)


class BoundedExecution(LiveExecutionClient):
    def __init__(self, context, **kwargs):
        super().__init__(client_id=ClientId("SIM"), venue=VENUE,
            oms_type=OmsType.NETTING, account_type=AccountType.CASH, base_currency=USD,
            instrument_provider=InstrumentProvider(), **kwargs)
        self.context = context
        context.execution = self
        self._set_account_id(AccountId("SIM-ALPACAPAPER"))  # alias, never actual account ID

    async def _connect(self):
        cash = Money(self.context.cash, USD)
        self.generate_account_state([AccountBalance(cash, Money(0, USD), cash)], [], True, self._clock.timestamp_ns())

    async def _disconnect(self):
        pass

    async def generate_order_status_report(self, command):
        raise PaperError("General reconciliation unsupported; use bounded broker receipt.")

    async def generate_order_status_reports(self, command):
        raise PaperError("Restart recovery unsupported.")

    async def generate_fill_reports(self, command):
        raise PaperError("Historical fill import unsupported.")

    async def generate_position_status_reports(self, command):
        raise PaperError("Existing positions are not supported by this flat-start test.")

    async def generate_mass_status(self, lookback_mins=None):
        raise PaperError("General reconciliation unsupported.")

    async def _submit_order(self, command):
        ctx, order = self.context, command.order
        client_id = "ntl-" + hashlib.sha256((str(ctx.root) + str(order.client_order_id)).encode()).hexdigest()[:32]
        body = {"symbol": "SPY", "qty": str(order.quantity), "side": "buy" if order.side == OrderSide.BUY else "sell",
                "type": "limit", "limit_price": str(order.price), "time_in_force": "day",
                "extended_hours": False, "client_order_id": client_id}
        entry = {"client_order_id": client_id, "side": body["side"], "status": "reserved"}
        try:
            if order.instrument_id != INSTRUMENT_ID or order.order_type != OrderType.LIMIT or order.time_in_force != TimeInForce.DAY:
                raise PaperError("Unsupported native order.")
            validate_order(body, ctx.position)
            if ctx.submissions >= 2 or ctx.unknown or not ctx.armed:
                raise PaperError("Submission bound reached.")
            clock = await asyncio.to_thread(ctx.api.request, "GET", "/v2/clock")
            if clock.get("is_open") is not True:
                raise PaperError("Market closed; order not sent.")
            if not ctx.fake:
                positions = await asyncio.to_thread(ctx.api.request, "GET", "/v2/positions")
                broker_qty = sum(Decimal(p["qty"]) for p in positions if p["symbol"] == "SPY")
                if any(p["symbol"] != "SPY" for p in positions) or broker_qty != ctx.position:
                    raise PaperError("Broker/native position disagreement.")
                validate_order(body, broker_qty)
            ctx.journal.append(entry)
            save(ctx.root / "journal.json", ctx.journal)  # durable before POST
            ctx.submissions += 1
            self.generate_order_submitted(order.strategy_id, order.instrument_id, order.client_order_id, self._clock.timestamp_ns())
            try:
                result = await asyncio.to_thread(ctx.api.request, "POST", "/v2/orders", body)
            except Exception:
                # A timeout is unknown, never a rejection or a reason to resubmit.
                ctx.unknown, ctx.armed = True, False
                entry["status"] = "unknown_submission"
                save(ctx.root / "journal.json", ctx.journal)
                return
            venue_id = VenueOrderId(result["id"])
            self.generate_order_accepted(order.strategy_id, order.instrument_id, order.client_order_id, venue_id, self._clock.timestamp_ns())
            entry.update(status="accepted", venue_order_id=result["id"])
            save(ctx.root / "journal.json", ctx.journal)
            filled_before = Decimal(0)
            for _ in range(15):
                if result.get("client_order_id") != client_id or result.get("symbol") != "SPY" or result.get("side") != body["side"]:
                    raise PaperError("Unexpected order response identity.")
                filled = Decimal(result["filled_qty"])
                if filled not in (Decimal(0), Decimal(1)) or filled < filled_before:
                    raise PaperError("Unexpected partial/cumulative fill; stop and reconcile manually.")
                if filled > filled_before:
                    px = Decimal(result["filled_avg_price"])
                    if not px.is_finite() or not 0 < px <= MAX_NOTIONAL:
                        raise PaperError("Unexpected fill price.")
                    self.generate_order_filled(order.strategy_id, order.instrument_id, order.client_order_id,
                        venue_id, None, TradeId(client_id), order.side, order.order_type,
                        Quantity.from_int(1), Price.from_str(str(px)), USD,
                        Money(0, USD), LiquiditySide.NO_LIQUIDITY_SIDE, self._clock.timestamp_ns())
                    ctx.position += 1 if order.side == OrderSide.BUY else -1
                    ctx.fills += 1
                    filled_before = filled
                    ctx.events.append({"type": "native_fill", "side": body["side"], "quantity": 1})
                state = result["status"]
                if state in ("filled", "canceled", "expired", "rejected"):
                    if state == "filled" and filled != 1:
                        raise PaperError("Terminal fill quantity mismatch.")
                    if state != "filled":
                        if state == "rejected":
                            self.generate_order_rejected(order.strategy_id, order.instrument_id, order.client_order_id, "Paper broker rejection", self._clock.timestamp_ns())
                        else:
                            self.generate_order_canceled(order.strategy_id, order.instrument_id, order.client_order_id, venue_id, self._clock.timestamp_ns())
                    entry["status"] = state
                    break
                await asyncio.sleep(0.1 if ctx.fake else 1)
                result = await asyncio.to_thread(ctx.api.by_client_id, client_id)
            else:
                # Cancel only this session's acknowledged order; never cancel all.
                await asyncio.to_thread(ctx.api.request, "DELETE", "/v2/orders/" + str(venue_id))
                entry["status"] = "cancel_requested_unconfirmed"
                ctx.unknown, ctx.armed = True, False
            save(ctx.root / "journal.json", ctx.journal)
        except Exception as error:
            if entry in ctx.journal:
                ctx.unknown, ctx.armed = True, False
                entry["status"] = "reconciliation_required"
                save(ctx.root / "journal.json", ctx.journal)
            else:
                self.generate_order_rejected(order.strategy_id, order.instrument_id, order.client_order_id, "Paper policy rejected", self._clock.timestamp_ns())
            ctx.events.append({"type": "execution_error", "error_type": type(error).__name__})
            if ctx.fake:
                ctx.events[-1]["fixture_error"] = str(error)
        finally:
            ctx.pending = False

    async def _cancel_order(self, command):
        raise PaperError("Use bounded session cleanup; arbitrary cancellation unsupported.")

    async def _cancel_all_orders(self, command):
        raise PaperError("Cancel-all is intentionally unsupported.")


def build_node(ctx):
    class DataFactory(LiveDataClientFactory):
        @staticmethod
        def create(loop, name, config, msgbus, cache, clock):
            return BoundedData(ctx, loop=loop, msgbus=msgbus, cache=cache, clock=clock)

    class ExecFactory(LiveExecClientFactory):
        @staticmethod
        def create(loop, name, config, msgbus, cache, clock):
            return BoundedExecution(ctx, loop=loop, msgbus=msgbus, cache=cache, clock=clock)

    # This is a new, bounded flat-start client. No existing reconciliation control
    # is changed. Native account balances mirror paper cash; margin is not enabled.
    config = TradingNodeConfig(trader_id="PAPER-001",
        logging=LoggingConfig(log_level="ERROR", log_colors=False),
        data_clients={"SIM": LiveDataClientConfig()}, exec_clients={"SIM": LiveExecClientConfig()},
        exec_engine=LiveExecEngineConfig(reconciliation=False, inflight_check_interval_ms=0),
        risk_engine=LiveRiskEngineConfig(max_notional_per_order={str(INSTRUMENT_ID): MAX_NOTIONAL}),
        timeout_connection=10, timeout_disconnection=2, timeout_post_stop=0)
    node = TradingNode(config=config)
    node.add_data_client_factory("SIM", DataFactory)
    node.add_exec_client_factory("SIM", ExecFactory)
    strategy = BoundedSPY(ctx)
    node.trader.add_strategy(strategy)
    node.build()
    return node, strategy


async def started_node(ctx):
    node, strategy = build_node(ctx)
    task = asyncio.create_task(node.run_async())
    for _ in range(100):
        if strategy.is_running:
            return node, strategy, task
        if task.done():
            await task
            raise PaperError("Native node stopped before strategy start.")
        await asyncio.sleep(0.1)
    await node.stop_async()
    await task
    raise PaperError("Native node startup timed out.")


async def stop_node(node, task):
    await node.stop_async()
    await task
    # asyncio.run owns this shared loop. TradingNode.dispose would stop it while
    # the caller is still running; dispose public kernel resources separately.
    node.kernel.dispose()
    if node.kernel.executor:
        node.kernel.executor.shutdown(wait=True, cancel_futures=True)
