# Bounded sector-momentum-v1: project-owned adapter; no optimization.
from AlgorithmImports import *
from collections import deque
from datetime import datetime, date
import math
import statistics
import json
import hashlib
MODE = "hold"  # hold, equal, momentum, gate; exactly four fixed cases.
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]

class GateCore:
    """Matches research.risk_gate: pandas adjust=False EMA seeded at first close."""
    def __init__(self):
        self.fast = self.slow = self.previous = None
        self.peak = 0.0
        self.n = 0
        self.returns = deque(maxlen=20)
        self.state = "unassessed"
        self.red_count = self.green_count = 0

    def update(self, value):
        close = round(float(value), 2)
        if self.previous is not None:
            self.returns.append(close / self.previous - 1)
        self.previous = close
        self.n += 1
        self.fast = close if self.fast is None else (2/51)*close + (1-2/51)*self.fast
        self.slow = close if self.slow is None else (2/201)*close + (1-2/201)*self.slow
        self.peak = max(self.peak, close)
        if self.n < 200 or len(self.returns) != 20:
            self.state = "unassessed"
            self.red_count = self.green_count = 0
            return
        dd = close/self.peak - 1
        vol = statistics.stdev(self.returns)*math.sqrt(252)
        positive = self.fast > self.slow
        red = dd < -.20 or vol >= .40
        yellow = not positive or dd <= -.10 or vol >= .25
        if self.state == "unassessed":
            self.state = "yellow"
        if red:
            self.state = "red"
            self.red_count = self.green_count = 0
        elif self.state == "red":
            self.red_count = self.red_count+1 if dd > -.18 and vol < .35 else 0
            self.green_count = 0
            if self.red_count >= 5:
                self.state = "yellow"
                self.red_count = 0
        else:
            if self.state == "green" and yellow:
                self.state = "yellow"
                self.green_count = 0
            if self.state == "yellow":
                self.green_count = self.green_count+1 if positive and dd > -.08 and vol < .20 else 0
                if self.green_count >= 5:
                    self.state = "green"
                    self.green_count = 0

    @property
    def cap(self):
        return {"unassessed":0., "green":1., "yellow":.5, "red":0.}[self.state]



"""Pure summary metrics; intended to execute inside QC on its private NAV path."""
from datetime import date
import math
import statistics


def summarize_path(rows, opening, anchor_date):
    if not rows or opening <= 0:
        raise ValueError('Need positive opening NAV and observations')
    dates = [date.fromisoformat(d) for d, _ in rows]
    values = [float(v) for _, v in rows]
    anchor = date.fromisoformat(anchor_date)
    if dates[0] <= anchor or any(b <= a for a, b in zip(dates, dates[1:])):
        raise ValueError('Dates must increase strictly after anchor')
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('Nonpositive or nonfinite NAV')
    previous = peak = float(opening)
    peak_date = anchor
    drawdown = 0.0
    returns = []
    underwater = longest = run = longest_days = 0
    for d, v in zip(dates, values):
        returns.append(v / previous - 1)
        previous = v
        if v >= peak:
            peak = v
            peak_date = d
            run = 0
        else:
            run += 1
            underwater += 1
            longest = max(longest, run)
            # Calendar days peak to last underwater mark, excludes recovery day.
            longest_days = max(longest_days, (d - peak_date).days)
        drawdown = min(drawdown, v / peak - 1)
    sd = statistics.stdev(returns) if len(returns) > 1 else 0
    sharpe = statistics.mean(returns) / sd * math.sqrt(252) if sd > 1e-15 else None
    total = values[-1] / opening - 1
    cagr = (values[-1] / opening) ** (365.25 / (dates[-1] - anchor).days) - 1
    return dict(n=len(rows), end=values[-1], ret=total, cagr=cagr, dd=drawdown,
                sharpe=sharpe, calmar=cagr / abs(drawdown) if drawdown < 0 else None,
                annual_calmar=total / abs(drawdown) if drawdown < 0 else None,
                uw=underwater, uw_fraction=underwater / len(rows),
                longest_uw=longest, longest_uw_days=longest_days,
                censored=values[-1] < peak,
                return_sum=sum(returns), return_square_sum=sum(r*r for r in returns))

class SectorComparison(QCAlgorithm):
    def initialize(self):
        if MODE not in ("hold", "equal", "momentum", "gate"):
            raise ValueError("Unsupported frozen case")
        self.set_start_date(2017, 1, 3)
        self.set_end_date(2025, 12, 31)
        self.set_cash(300000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.settings.daily_precise_end_time = True
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)
        self.symbols = {}
        self.last = {}
        self.last_dates = {}
        for ticker in ["SPY"] + SECTORS:
            sec = self.add_equity(ticker, Resolution.DAILY, data_normalization_mode=DataNormalizationMode.RAW)
            sec.set_leverage(2)  # Pending-sale credit only; 98% targets and closing no-borrow checks remain.
            sec.set_fee_model(ConstantFeeModel(1))
            sec.set_slippage_model(ConstantSlippageModel(.0005))
            self.symbols[ticker] = sec.symbol
            history = list(self.history[TradeBar](sec.symbol, 2, Resolution.DAILY))
            if not history:
                raise ValueError("Missing initial raw history: " + ticker)
            bar = history[-1]
            if bar.time.date() >= self.time.date():
                raise ValueError("Warm-up overlaps evaluation")
            sec.set_market_price(bar)
            self.last[ticker] = float(bar.close)
            self.last_dates[ticker] = bar.time.date()
        self._spy = self.symbols["SPY"]
        self.set_benchmark(self._spy)
        self.core = GateCore()
        for bar in self.history[TradeBar](self._spy, datetime(2004,1,2), datetime(2017,1,3), Resolution.DAILY):
            self.core.update(bar.close)
        if self.core.n < 200:
            raise ValueError("Gate warmup incomplete")
        self.curve = []
        self.entered = False
        self.month = None
        self.invalid_orders = self.dividends = self.splits = self.rebalances = 0
        self.min_cash = 300000.
        self.max_gross = 0.
        self.coverage_hash = hashlib.sha256()
        self.schedule.on(self.date_rules.every_day(self._spy),
                         self.time_rules.before_market_open(self._spy, 30), self.rebalance)

    def rebalance(self):
        if self.transactions.get_open_orders():
            raise ValueError("Unresolved previous order")
        if any(d >= self.time.date() for d in self.last_dates.values()):
            raise ValueError("Sizing data is not from a completed session")
        if MODE == "hold":
            if self.entered:
                return
            weights = {"SPY": 1.}
        elif MODE == "gate":
            weights = {"SPY": self.core.cap}
        else:
            month = (self.time.year, self.time.month)
            if month == self.month:
                return
            self.month = month
            selected = list(SECTORS)
            if MODE == "momentum":
                h = self.history([self.symbols[t] for t in SECTORS], 253, Resolution.DAILY,
                                 fill_forward=False, data_normalization_mode=DataNormalizationMode.TOTAL_RETURN)
                scores = []
                for ticker in SECTORS:
                    frame = h.loc[self.symbols[ticker]]
                    if len(frame) != 253 or frame.index[-1].date() >= self.time.date():
                        raise ValueError("Incomplete/forward momentum lookback: " + ticker)
                    if not frame.index.equals(h.loc[self.symbols[SECTORS[0]]].index):
                        raise ValueError("Momentum calendars differ")
                    prices = frame["close"].to_numpy()
                    if not all(math.isfinite(float(x)) and x > 0 for x in prices):
                        raise ValueError("Invalid momentum input")
                    scores.append((ticker, float(prices[-1] / prices[0] - 1)))
                selected = [t for t, score in sorted(scores, key=lambda x: (-x[1], x[0]))[:3]]
            weights = {t: 1. / len(selected) for t in selected}
        nav = float(self.portfolio.total_portfolio_value)
        orders = []
        for ticker, symbol in self.symbols.items():
            target = math.floor(nav * .98 * weights.get(ticker, 0.) / self.last[ticker])
            delta = target - int(self.portfolio[symbol].quantity)
            if delta:
                orders.append((delta, ticker, symbol))
        # Sales precede purchases; margin plumbing permits proceeds reuse, not a borrowing mandate.
        for delta, ticker, symbol in sorted(orders, key=lambda x: (x[0] > 0, x[1])):
            self.market_on_open_order(symbol, delta, tag="sector-v1:" + MODE)
        self.rebalances += 1
        if MODE == "hold":
            self.entered = True

    def on_data(self, data):
        self.dividends += sum(1 for _ in data.dividends)
        self.splits += sum(1 for _ in data.splits)
        for ticker, symbol in self.symbols.items():
            if symbol in data.splits and data.splits[symbol].type == SplitType.SPLIT_OCCURRED:
                self.last[ticker] *= float(data.splits[symbol].split_factor)
        if self._spy not in data.bars:
            return
        session = data.bars[self._spy].time.date()
        if self.curve and str(session) <= self.curve[-1][0]:
            raise ValueError("Duplicate NAV session")
        for ticker, symbol in self.symbols.items():
            if symbol not in data.bars or data.bars[symbol].time.date() != session:
                raise ValueError("Missing shared bar: " + ticker)
            self.last[ticker] = float(data.bars[symbol].close)
            self.last_dates[ticker] = session
        self.core.update(self.last["SPY"])
        nav = float(self.portfolio.total_portfolio_value)
        cash = float(self.portfolio.cash)
        gross = sum(abs(float(self.portfolio[s].holdings_value)) for s in self.symbols.values()) / nav
        if not math.isfinite(nav) or nav <= 0 or cash < -.01 or gross > 1.000001:
            raise ValueError("Invalid NAV, negative cash, or leverage")
        if any(self.portfolio[s].quantity < 0 for s in self.symbols.values()):
            raise ValueError("Short position")
        self.min_cash = min(self.min_cash, cash)
        self.max_gross = max(self.max_gross, gross)
        self.coverage_hash.update((str(session) + "\n").encode())
        self.curve.append((str(session), nav))

    def on_order_event(self, event):
        if event.status == OrderStatus.INVALID:
            self.invalid_orders += 1
            raise ValueError("Rejected simulated order: " + str(event))

    def on_end_of_algorithm(self):
        # Export summaries only. Daily NAV and source market data remain inside QC.
        previous = 300000.
        anchor = "2016-12-30"
        global_peak = 300000.
        for year in sorted({d[:4] for d,v in self.curve}):
            rows = [(d,v) for d,v in self.curve if d.startswith(year)]
            result = summarize_path(rows, previous, anchor)
            global_uw = 0
            for d, v in rows:
                global_peak = max(global_peak, v)
                global_uw += int(v < global_peak)
            result.update(study="sector-v1", mode=MODE, year=year,
                          global_uw=global_uw, global_uw_fraction=global_uw/len(rows))
            self.log(json.dumps(result, separators=(",", ":"), allow_nan=False))
            previous = rows[-1][1]
            anchor = rows[-1][0]
        if self.curve:
            result = summarize_path(self.curve, 300000., "2016-12-30")
            result.update(study="sector-v1", mode=MODE, year="ALL", rejects=self.invalid_orders,
                          dividends=self.dividends, splits=self.splits, rebalances=self.rebalances,
                          min_cash=self.min_cash, max_gross=self.max_gross,
                          calendar_hash=self.coverage_hash.hexdigest(),
                          first=self.curve[0][0], last=self.curve[-1][0],
                          fees=float(self.portfolio.total_fees))
            self.log(json.dumps(result, separators=(",", ":"), allow_nan=False))
