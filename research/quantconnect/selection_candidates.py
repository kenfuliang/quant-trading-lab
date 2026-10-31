"""Project-owned, source-informed selection rules for the frozen QC breadth study.
Not exact reproductions of legacy tutorial examples; see dated intake receipt.
"""
from AlgorithmImports import *
from collections import deque
from datetime import date, datetime
import math, statistics, hashlib, json

MODE='asset'

def percent_momentum(closes):
    return closes[-1]/closes[0]-1

def return_volatility(closes):
    return statistics.stdev([b/a-1 for a,b in zip(closes,closes[1:])])

class SelectionComparison(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2020,1,1)
        self.set_end_date(2025,12,31)
        self.set_cash(10000)
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,AccountType.MARGIN)
        self.settings.minimum_order_margin_portfolio_percentage=0.
        self.set_benchmark('SPY')
        self._syms={'SPY':self.add_equity('SPY',Resolution.DAILY).symbol}
        self._selected=[];self._weights={};self._series={};self._last_bar={}
        self._universe_month=None;self._decision_month=None
        self._selection_events=0;self._universe_calls=0;self._fundamental_valid=0
        self._history_seeded=0;self._history_short=0;self._ready_counts=[]
        self._membership_hash=hashlib.sha256()
        self.universe_settings.resolution=Resolution.DAILY
        self.universe_settings.asynchronous=False
        if MODE=='asset':
            for ticker in ['EFA','BND','VNQ','GSG']:
                self._syms[ticker]=self.add_equity(ticker,Resolution.DAILY).symbol
            self._selected=list(self._syms.values())
        elif MODE in ('momentum','lowvol'):
            self.add_universe(self.select_universe)
        self.add_security_initializer(self.configure_security)
        for sym in self._syms.values():self.configure_security(self.securities[sym])
        self._fund_initialize()
        self._audit_initialize()

    def configure_security(self,security):
        if type(security.fee_model).__name__!='InteractiveBrokersFeeModel':
            raise ValueError('Native IB fee model not retained')
        security.set_slippage_model(ConstantSlippageModel(.0025))
        security.set_margin_interest_rate_model(MarginInterestRateModel.NULL)

    def select_universe(self,fundamentals):
        # Original momentum screens monthly; low-volatility screens daily.
        month=(self.time.year,self.time.month)
        if MODE=='momentum' and month==self._universe_month:
            return Universe.UNCHANGED
        self._universe_month=month;self._universe_calls+=1
        valid=[f for f in fundamentals if f.has_fundamental_data and math.isfinite(float(f.price)) and f.price>5 and math.isfinite(float(f.dollar_volume)) and f.dollar_volume>0]
        liquid=sorted(valid,key=lambda f:(-float(f.dollar_volume),str(f.symbol.id)))[:100]
        large=[f for f in liquid if math.isfinite(float(f.market_cap)) and f.market_cap>0]
        self._fundamental_valid+=len(large)
        self._selected=[f.symbol for f in sorted(large,key=lambda f:(-float(f.market_cap),str(f.symbol.id)))[:50]]
        self._membership_hash.update((str(self.time.date())+':'+'|'.join(str(s.id) for s in self._selected)+'\n').encode())
        # Keep monthly targets subscribed even when the daily ranking changes.
        if MODE=='lowvol':return list(dict.fromkeys(self._selected+list(self._weights)))
        return self._selected

    def on_securities_changed(self,changes):
        for security in changes.added_securities:
            if security.symbol not in self._syms.values():
                self._syms[str(security.symbol.id)]=security.symbol
            self.configure_security(security)

    def _update_series(self,data):
        # Rebuild each monthly feature window in one normalization basis below.
        pass

    def _refresh_weights(self,data):
        month=(self.time.year,self.time.month)
        if month==self._decision_month:return
        self._decision_month=month;self._selection_events+=1
        if MODE=='spy':
            self._weights={self._syms['SPY']:1.};return
        self._fund_intent=None # Monthly equal-weight rebalance even if names unchanged.
        self._series={s:deque(maxlen=253) for s in self._selected};self._last_bar={}
        history=self.history[TradeBar](self._selected,253,Resolution.DAILY,data_normalization_mode=DataNormalizationMode.SCALED_RAW)
        for bars in history:
            for symbol,bar in bars.items():
                if symbol not in self._series:continue
                if bar.end_time>self.time:raise ValueError('Future feature bar')
                self._series[symbol].append(float(bar.close));self._last_bar[symbol]=bar.end_time
        self._history_seeded+=len(self._selected)
        self._history_short+=sum(len(v)<253 for v in self._series.values())
        ready=[s for s in self._selected if len(self._series.get(s,[]))==253 and s in data.bars and self._last_bar[s]==data.bars[s].end_time]
        self._ready_counts.append(len(ready))
        count=3 if MODE=='asset' else 5
        if MODE=='lowvol':
            selected=sorted(ready,key=lambda s:(return_volatility(list(self._series[s])),str(s.id)))[:count]
        else:
            selected=sorted(ready,key=lambda s:(-percent_momentum(list(self._series[s])),str(s.id)))[:count]
        self._weights={s:1./count for s in selected}

    def _t10_weights(self):return self._weights
    def _t11_weights(self):return {}
    def _s2_weights(self):return {}
    def _s3_weights(self):return {}

    def on_data(self,data):
        if self.is_warming_up or self._syms['SPY'] not in data.bars:return
        self._update_series(data)
        self._refresh_weights(data)
        self._fund_accrue(data.bars[self._syms['SPY']].time.date())
        self._funded_rebalance()
        self._audit_record(data)
        self._fund_cash=float(self.portfolio.cash)

    def on_order_event(self,event):self._audit_order(event)
    def on_end_of_algorithm(self):self._audit_end()
