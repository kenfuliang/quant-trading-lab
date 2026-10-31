"""Synthetic transport fixture for native integration; never a brokerage client."""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from pathlib import Path
import tempfile

from nautilus_trader.model.data import Bar, QuoteTick
from nautilus_trader.model.objects import Price, Quantity
from research.spy_backtest import BAR_TYPE, INSTRUMENT_ID
from paper_trading.alpaca import check_quote, validate_order, PaperError
from paper_trading.alpaca_native import Context, started_node, stop_node


class FakePaper:
    def __init__(self, timeout=False, closed=False, partial=False):
        self.posts = []
        self.timeout, self.closed = timeout, closed
        self.partial = partial

    def request(self, method, path, body=None):
        if path == "/v2/clock":
            return {"is_open": not self.closed}
        if method == "POST":
            self.posts.append(body)
            if self.timeout:
                raise TimeoutError("unknown")
            return {"id": "fake-" + str(len(self.posts)), "client_order_id": body["client_order_id"],
                    "symbol": "SPY", "side": body["side"], "status": "partially_filled" if self.partial else "filled",
                    "filled_qty": "0.5" if self.partial else "1", "filled_avg_price": "100.00"}
        raise AssertionError((method, path))


def quote():
    ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
    return QuoteTick(INSTRUMENT_ID, Price.from_str("99.99"), Price.from_str("100.00"),
                     Quantity.from_int(100), Quantity.from_int(100), ns, ns)


async def wait_until(predicate):
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(.02)
    raise AssertionError("native event did not complete")


async def native_fixture(root, *, timeout=False, closed=False, partial=False, saved_spy=False):
    ctx = Context(FakePaper(timeout=timeout, closed=closed, partial=partial), root, fake=True)
    node, strategy, task = await started_node(ctx)
    try:
        # Native Strategy.on_bar is the existing ComparisonStrategy method.
        base = datetime.now(timezone.utc) - timedelta(days=400)
        if saved_spy:
            from research.spy_backtest import load_data
            path = Path(__file__).resolve().parents[1] / "reports/spy/20261024-235746-728801/source-data.json"
            frame, _, _ = load_data(path)
            warmup = frame.loc[:"2019-12-31"].tail(250)
            exit_rows = frame.loc["2020-01-02":"2020-03-31"]
        else:
            warmup = exit_rows = None
        for i in range(250):
            ns = int((base + timedelta(days=i)).timestamp()) * 1_000_000_000
            price = Price.from_str(f"{warmup.iloc[i].close if saved_spy else 100 + i / 10:.2f}")
            ctx.data.feed(Bar(BAR_TYPE, price, price, price, price, Quantity.from_int(10), ns, ns))
        await wait_until(lambda: strategy.slow.initialized)
        assert strategy.want_long
        ctx.armed = True
        ctx.data.feed(quote())
        if closed:
            await wait_until(lambda: bool(ctx.events))
            await asyncio.sleep(.1)
        elif timeout or partial:
            await wait_until(lambda: ctx.unknown)
            ctx.data.feed(quote())
            await asyncio.sleep(.1)
        else:
            await wait_until(lambda: ctx.fills == 1)
            await asyncio.sleep(.1)
            assert Decimal(str(strategy.portfolio.net_position(INSTRUMENT_ID))) == 1
            # Same desired position must not submit a duplicate.
            ctx.data.feed(quote())
            await asyncio.sleep(.1)
            for i in range(250, 250 + (len(exit_rows) if saved_spy else 100)):
                ns = int((base + timedelta(days=i)).timestamp()) * 1_000_000_000
                price = Price.from_str(f"{exit_rows.iloc[i-250].close:.2f}" if saved_spy else "10.00")
                ctx.data.feed(Bar(BAR_TYPE, price, price, price, price, Quantity.from_int(10), ns, ns))
            await wait_until(lambda: not strategy.want_long)
            ctx.data.feed(quote())
            await wait_until(lambda: ctx.fills == 2)
            await asyncio.sleep(.1)
            assert Decimal(str(strategy.portfolio.net_position(INSTRUMENT_ID))) == 0
        result = {"kind": "offline_native_with_fake_alpaca", "submissions": ctx.submissions,
                  "native_fills": ctx.fills, "unknown": ctx.unknown,
                  "broker_post_count": len(ctx.api.posts), "events": ctx.events,
                  "ending_native_position": str(strategy.portfolio.net_position(INSTRUMENT_ID)),
                  "signal_input": "saved_SPY_250_bars_to_2019_end_then_2020Q1" if saved_spy else "synthetic",
                  "timestamps": "synthetic_in_both_fixtures", "fake_fill_price": "fixed_100USD_not_historical_execution"}
        if saved_spy:
            from research.alpaca_pilot import digest
            result["source_data_sha256"] = digest(path)
        return result
    finally:
        (Path(root) / "native-events.json").write_text(json.dumps({"events": ctx.events,
            "journal": ctx.journal, "submissions": ctx.submissions, "fills": ctx.fills}, indent=2))
        await stop_node(node, task)


