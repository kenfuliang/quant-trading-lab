"""SPY EMA50/200 versus buy-and-hold, executed by NautilusTrader.

Prices are Yahoo daily OHLC; synthetic open/close quotes implement explicit
spread/slippage. These quotes are NOT historical quote observations.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from nautilus_trader.backtest.config import BacktestEngineConfig, SimulationModuleConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import FixedFeeModel
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.config import LoggingConfig, StrategyConfig
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType, QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy

INITIAL_CASH = 100_000.0
START = "2005-01-01"
END = "2025-12-31"
FAST = 50
SLOW = 200
COST_BPS = 5.0  # Combined half-spread/slippage per side, illustrative.
COMMISSION = 1.0
ALLOCATION = 0.99
VENUE = Venue("SIM")
INSTRUMENT_ID = InstrumentId.from_str("SPY.SIM")
BAR_TYPE = BarType.from_str("SPY.SIM-1-DAY-LAST-EXTERNAL")
SOURCE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1=1072915200&period2=1767225600&interval=1d&events=div%2Csplits"


def load_data(path: Path):
    raw = path.read_bytes()
    payload = json.loads(raw)["chart"]
    if payload.get("error"):
        raise ValueError(str(payload["error"]))
    result = payload["result"][0]
    if result["meta"]["symbol"] != "SPY":
        raise ValueError("Expected SPY data.")
    if result.get("events", {}).get("splits"):
        raise ValueError("Split handling is not implemented; refusing this dataset.")
    dates = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert("America/New_York").strftime("%Y-%m-%d")
    frame = pd.DataFrame(result["indicators"]["quote"][0], index=pd.Index(dates, name="date"))
    frame = frame[["open", "high", "low", "close", "volume"]]
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Dates must be unique and sorted.")
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Missing or non-finite OHLCV data.")
    if (frame <= 0).any().any():
        raise ValueError("Prices and volumes must be positive.")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
            (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC ordering.")
    if len(frame.loc[:START]) < SLOW:
        raise ValueError("Insufficient warm-up history.")
    dividends = {}
    for item in result.get("events", {}).get("dividends", {}).values():
        date = pd.Timestamp(item["date"], unit="s", tz="UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")
        if date not in frame.index or item["amount"] <= 0:
            raise ValueError("Invalid or unmatched dividend event.")
        dividends[date] = dividends.get(date, 0) + item["amount"]
    metadata = {
        "source": "Yahoo Finance chart endpoint; retail research data, not independently reconciled",
        "source_url": SOURCE_URL, "sha256": hashlib.sha256(raw).hexdigest(),
        "raw_rows": len(frame), "first_date": frame.index[0], "last_date": frame.index[-1],
        "dividend_events": len(dividends), "split_events": 0,
    }
    return frame, dividends, metadata


def instrument():
    return Equity(INSTRUMENT_ID, Symbol("SPY"), USD, 2, Price.from_str("0.01"),
                  Quantity.from_int(1), 0, 0)


def price(value):
    return Price.from_str(f"{value:.2f}")


def execution_price(value, side, cost_bps=COST_BPS):
    sign = 1 if side == "BUY" else -1
    return round(float(value) * (1 + sign * cost_bps / 10_000), 2)


def make_events(frame, cost_bps=COST_BPS):
    events = []
    for date, row in frame.iterrows():
        opened = pd.Timestamp(f"{date} 09:30", tz="America/New_York").value
        closed = pd.Timestamp(f"{date} 16:00", tz="America/New_York").value
        for timestamp, mark in ((opened, row.open), (closed - 1, row.close)):
            events.append(QuoteTick(INSTRUMENT_ID,
                price(execution_price(mark, "SELL", cost_bps)),
                price(execution_price(mark, "BUY", cost_bps)),
                Quantity.from_int(1_000_000), Quantity.from_int(1_000_000), timestamp, timestamp))
        events.append(Bar(BAR_TYPE, price(row.open), price(row.high), price(row.low),
                          price(row.close), Quantity.from_int(int(row.volume)), closed, closed))
    return events


class DividendModule(SimulationModule):
    """Credit dividends on ex-date before open trading, using prior holdings.

    Payment-date timing and withholding taxes are deliberately not modeled.
    """
    def __init__(self, dividends):
        super().__init__(SimulationModuleConfig())
        self.dividends = dividends
        self.processed = set()
        self.records = []

    def pre_process(self, data):
        date = pd.Timestamp(data.ts_event, tz="UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")
        if date in self.processed:
            return
        self.processed.add(date)
        if date not in self.dividends:
            return
        qty = sum(p.quantity.as_double() for p in self.exchange.cache.positions_open(instrument_id=INSTRUMENT_ID))
        credit = Money(qty * self.dividends[date], USD)
        if credit.as_double():
            self.exchange.adjust_account(credit)
            self.records.append({"date": date, "shares": qty, "per_share": self.dividends[date], "cash": credit.as_double()})

    def process(self, ts_now):
        pass

    def log_diagnostics(self, logger):
        pass

    def reset(self):
        self.processed.clear()
        self.records.clear()


class ComparisonConfig(StrategyConfig, frozen=True):
    mode: str = "trend"
    start: str = START
    end: str = END
    fast: int = FAST
    slow: int = SLOW


class ComparisonStrategy(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.fast = ExponentialMovingAverage(config.fast)
        self.slow = ExponentialMovingAverage(config.slow)
        self.want_long = False
        self.rows = []
        self.last_open_date = None

    def on_start(self):
        self.subscribe_quote_ticks(INSTRUMENT_ID)
        self.subscribe_bars(BAR_TYPE)

    def on_quote_tick(self, tick):
        time = pd.Timestamp(tick.ts_event, tz="UTC").tz_convert("America/New_York")
        date = time.strftime("%Y-%m-%d")
        if (time.hour, time.minute, time.second) != (9, 30, 0):
            return
        if not self.config.start <= date <= self.config.end or date == self.last_open_date:
            return
        self.last_open_date = date
        if self.config.mode == "trend" and not self.slow.initialized:
            return
        desired = self.config.mode == "buy_hold" or self.want_long
        qty = float(self.portfolio.net_position(INSTRUMENT_ID))
        if desired and qty == 0:
            cash = self.cache.account_for_venue(VENUE).balance_total(USD).as_double()
            count = math.floor((cash * ALLOCATION - COMMISSION) / tick.ask_price.as_double())
            if count > 0:
                self.submit_order(self.order_factory.market(INSTRUMENT_ID, OrderSide.BUY, Quantity.from_int(count)))
        elif not desired and qty > 0:
            self.close_all_positions(INSTRUMENT_ID)

    def on_bar(self, bar):
        # Daily indicators are updated only after the completed daily bar arrives.
        self.fast.update_raw(bar.close.as_double())
        self.slow.update_raw(bar.close.as_double())
        self.want_long = self.fast.value > self.slow.value
        date = pd.Timestamp(bar.ts_event, tz="UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")
        if self.config.start <= date <= self.config.end:
            cash = self.cache.account_for_venue(VENUE).balance_total(USD).as_double()
            qty = float(self.portfolio.net_position(INSTRUMENT_ID))
            mark = bar.close.as_double()
            self.rows.append({"date": date, "cash": cash, "shares": qty, "close": mark,
                              "equity": cash + qty * mark, "fast_ema": self.fast.value,
                              "slow_ema": self.slow.value, "next_open_long": self.want_long})


def run_engine(frame, dividends, mode, *, start=START, end=END, fast=FAST, slow=SLOW, cost_bps=COST_BPS):
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR", bypass_logging=True)))
    dividend_module = DividendModule(dividends)
    engine.add_venue(VENUE, OmsType.NETTING, AccountType.CASH,
        [Money(INITIAL_CASH, USD)], base_currency=USD, modules=[dividend_module],
        fee_model=FixedFeeModel(Money(COMMISSION, USD)), bar_execution=False,
        allow_cash_borrowing=False)
    engine.add_instrument(instrument())
    engine.add_data(make_events(frame.loc[:end], cost_bps))
    strategy = ComparisonStrategy(ComparisonConfig(mode=mode, start=start, end=end, fast=fast, slow=slow))
    engine.add_strategy(strategy)
    try:
        engine.run()
        curve = pd.DataFrame(strategy.rows).set_index("date")
        fills = engine.trader.generate_order_fills_report()
        orders = engine.trader.generate_orders_report()
        credits = pd.DataFrame(dividend_module.records, columns=["date", "shares", "per_share", "cash"])
        if not orders.empty and orders["status"].astype(str).isin(["REJECTED", "DENIED", "CANCELED"]).any():
            raise AssertionError("Unexpected unfilled/rejected orders.")
        return curve, fills, credits, orders
    finally:
        engine.dispose()


def metrics(curve, fills, credits):
    equity = curve.equity
    extended = np.r_[INITIAL_CASH, equity.to_numpy()]
    returns = extended[1:] / extended[:-1] - 1
    years = (pd.Timestamp(curve.index[-1]) - pd.Timestamp(curve.index[0])).days / 365.25
    drawdown = extended / np.maximum.accumulate(extended) - 1
    return {"ending_equity": float(equity.iloc[-1]), "total_return_pct": float((equity.iloc[-1] / INITIAL_CASH - 1) * 100),
            "cagr_pct": float(((equity.iloc[-1] / INITIAL_CASH) ** (1 / years) - 1) * 100),
            "max_drawdown_pct": float(drawdown.min() * 100),
            "annualized_volatility_pct": float(np.std(returns, ddof=1) * np.sqrt(252) * 100),
            "sharpe_zero_rf": float(np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252)),
            "exposure_days_pct": float((curve.shares > 0).mean() * 100),
            "filled_orders": len(fills), "dividend_cash": float(credits.cash.sum()) if not credits.empty else 0.0,
            "commission_usd": len(fills) * COMMISSION,
            "sessions": len(curve)}


def audit_run(frame, dividends, mode, curve, fills, credits, *, cost_bps=COST_BPS, fast=FAST, slow=SLOW):
    """Independent pandas/Decimal ledger: timing, signal, sizing, dividends, MTM."""
    work = frame.copy()
    work["fast"] = work.close.round(2).ewm(span=fast, adjust=False).mean()
    work["slow"] = work.close.round(2).ewm(span=slow, adjust=False).mean()
    desired = (work.fast > work.slow).shift(1, fill_value=False)
    checked_fills = fills.copy()
    if not checked_fills.empty:
        checked_fills["date"] = pd.to_datetime(checked_fills.ts_last, utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
        local_times = pd.to_datetime(checked_fills.ts_last, utc=True).dt.tz_convert("America/New_York").dt.strftime("%H:%M:%S")
        if not local_times.eq("09:30:00").all():
            raise AssertionError("A fill occurred outside the modeled open.")
        checked_fills["reference_open"] = [float(frame.loc[d, "open"]) for d in checked_fills.date]
        checked_fills["modeled_cost_vs_open_usd"] = [
            abs(float(r.avg_px) - r.reference_open) * float(r.filled_qty)
            for r in checked_fills.itertuples()]
        checked_fills["commission_usd"] = COMMISSION
        previous_dates = dict(zip(frame.index[1:], frame.index[:-1]))
        checked_fills["signal_date"] = [previous_dates[d] if mode == "trend" else "scheduled_start" for d in checked_fills.date]
    cash = Decimal(str(INITIAL_CASH))
    shares = 0
    max_error = 0.0
    dividend_cash = Decimal("0")
    expected_fill_count = 0
    for date, actual in curve.iterrows():
        if date in dividends:
            credit = Decimal(str(shares * dividends[date])).quantize(Decimal(".01"))
            cash += credit
            dividend_cash += credit
        today = checked_fills.loc[checked_fills.date == date] if not checked_fills.empty else checked_fills
        target = mode == "buy_hold" or bool(desired.loc[date])
        expected_side = "BUY" if target and not shares else "SELL" if not target and shares else None
        if len(today) != int(expected_side is not None):
            raise AssertionError(f"Signal/fill mismatch at {date}: {mode}")
        if expected_side:
            expected_fill_count += 1
            fill = today.iloc[0]
            px = execution_price(frame.loc[date, "open"], expected_side, cost_bps)
            qty = math.floor((float(cash) * ALLOCATION - COMMISSION) / px) if expected_side == "BUY" else shares
            if str(fill.side) != expected_side or int(fill.filled_qty) != qty or abs(float(fill.avg_px) - px) > 1e-8:
                raise AssertionError(f"Independent fill mismatch on {date}")
            movement = Decimal(qty) * Decimal(str(px))
            cash += (-movement if expected_side == "BUY" else movement) - Decimal(str(COMMISSION))
            shares = qty if expected_side == "BUY" else 0
        expected_equity = float(cash) + shares * round(float(frame.loc[date, "close"]), 2)
        error = max(abs(actual.equity - expected_equity), abs(actual.cash - float(cash)))
        max_error = max(max_error, error)
        if error > 0.05 or actual.shares != shares or actual.cash < -0.01:
            raise AssertionError(f"Daily ledger mismatch at {date}: {error=}")
    actual_dividends = credits.cash.sum() if not credits.empty else 0
    if abs(float(dividend_cash) - actual_dividends) > 0.05:
        raise AssertionError("Dividend entitlement mismatch.")
    return checked_fills, {
        "passed": True, "independently_checked_sessions": len(curve),
        "independently_checked_fills": expected_fill_count,
        "maximum_cash_or_equity_difference_usd": max_error,
        "checks": ["prior-close signal/next-open fill", "whole-share sizing", "per-order fee",
                   "spread/slippage fill price", "prior-session dividend entitlement", "daily cash and mark-to-market equity", "no cash borrowing"],
    }
