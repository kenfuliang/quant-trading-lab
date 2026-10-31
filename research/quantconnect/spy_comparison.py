# QuantConnect Cloud adapter: development diagnostic, not engine parity proof.
from AlgorithmImports import *
from collections import deque
from datetime import datetime
import math
import statistics
import json

MODE = "hold"  # Exactly one of hold, ema, gate; three separate bounded runs.


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


class SpyComparison(QCAlgorithm):
    def initialize(self):
        if MODE not in ("hold", "ema", "gate"):
            raise ValueError("Unsupported frozen case")
        self.set_start_date(2005, 1, 3)
        self.set_end_date(2025, 12, 31)
        self.set_cash(300000)
        self.set_time_zone(TimeZones.NEW_YORK)
        self.settings.daily_precise_end_time = True
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.CASH)
        security = self.add_equity("SPY", Resolution.DAILY, data_normalization_mode=DataNormalizationMode.RAW)
        self._spy = security.symbol
        security.set_leverage(1)
        security.set_fee_model(ConstantFeeModel(1))
        security.set_slippage_model(ConstantSlippageModel(.0005))
        self.set_benchmark(self._spy)
        self.core = GateCore()
        self.last_close = None
        self.last_session = None
        self.entered = False
        self.curve = []
        self.dividend_count = self.split_count = self.invalid_orders = 0
        # Explicit original warm-up origin preserves expanding peak and EMA seed.
        for bar in self.history[TradeBar](self._spy, datetime(2004,1,2), datetime(2005,1,3), Resolution.DAILY):
            self.core.update(bar.close)
            self.last_close = round(float(bar.close), 2)
            self.last_session = bar.time.date()
        if self.core.n < 200:
            raise ValueError("Insufficient explicit 2004 warm-up")
        # Seed only the last historical bar; no evaluation-day prices are used.
        security.set_market_price(bar)
        self.schedule.on(self.date_rules.every_day(self._spy),
                         self.time_rules.before_market_open(self._spy, 30), self.rebalance)

    def rebalance(self):
        if self.last_close is None or self.last_session >= self.time.date():
            raise ValueError("No completed prior session for execution")
        if self.transactions.get_open_orders(self._spy):
            raise ValueError("Unresolved prior order")
        qty = int(self.portfolio[self._spy].quantity)
        if MODE == "hold":
            if self.entered:
                return
            cap = 1.
        elif MODE == "ema":
            cap = float(self.core.n >= 200 and self.core.fast > self.core.slow)
            if cap and qty > 0:
                return
        else:
            cap = self.core.cap
        # Prior-close sizing: never look at the forthcoming opening price.
        # 1% cash buffer; gaps can reject an order and are reported, not hidden.
        target = math.floor(float(self.portfolio.total_portfolio_value)*.99*cap/self.last_close)
        delta = target-qty
        if delta:
            self.market_on_open_order(self._spy, delta, tag=MODE+":"+self.core.state)
            if MODE == "hold":
                self.entered = True

    def on_data(self, data):
        if self._spy in data.dividends:
            self.dividend_count += 1
        if self._spy in data.splits:
            self.split_count += 1
        if self._spy not in data.bars:
            return
        bar = data.bars[self._spy]
        self.core.update(bar.close)
        self.last_close = round(float(bar.close), 2)
        self.last_session = bar.time.date()
        self.curve.append((str(self.last_session), float(self.portfolio.total_portfolio_value)))
        if len(self.curve) % 5 == 0:
            self.plot("Risk gate", "Exposure cap", self.core.cap)

    def on_order_event(self, event):
        if event.status == OrderStatus.INVALID:
            self.invalid_orders += 1
            self.error("Rejected simulated order: "+str(event))

    def on_end_of_algorithm(self):
        # Small annual summaries fit free-tier logs; native report owns its metrics.
        previous = 300000.
        for year in sorted({d[:4] for d,v in self.curve}):
            values = [v for d,v in self.curve if d.startswith(year)]
            peak = previous
            dd = 0.
            for v in values:
                peak = max(peak,v)
                dd = min(dd,v/peak-1)
            self.log(json.dumps(dict(mode=MODE, year=year, annual_return=values[-1]/previous-1,
                                     within_year_max_drawdown=dd), separators=(",",":")))
            previous = values[-1]
        self.log(json.dumps(dict(mode=MODE, sessions=len(self.curve), dividends=self.dividend_count,
                                 splits=self.split_count, rejected_orders=self.invalid_orders,
                                 policy="raw;USD1/order;5bps;prior-close-sized next MOO;99pct;cash;no interest")))
