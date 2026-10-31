"""Bounded order-free hosted data access check, no raw-data export."""
from AlgorithmImports import *
import math,json
class AccessProbe(QCAlgorithm):
 def initialize(self):
  self.set_start_date(2020,1,1);self.set_end_date(2020,1,10);self.set_cash(10000)
  self.syms=[self.add_equity(t,Resolution.DAILY).symbol for t in ['SPY','EFA','BND','VNQ','GSG']]
  self.universe_settings.resolution=Resolution.DAILY;self.universe_settings.asynchronous=False
  self.add_universe(self.select);self.selected=[];self.calls=0;self.valid=0;self.checked=False
 def select(self,values):
  rows=[f for f in values if f.has_fundamental_data and f.price>5 and f.dollar_volume>0 and math.isfinite(float(f.market_cap)) and f.market_cap>0]
  liquid=sorted(rows,key=lambda f:-f.dollar_volume)[:100];self.selected=[f.symbol for f in sorted(liquid,key=lambda f:-f.market_cap)[:50]]
  self.calls+=1;self.valid=len(rows);return self.selected
 def on_data(self,data):
  if self.checked or len(self.selected)!=50 or not all(s in data.bars for s in self.syms):return
  symbols=self.syms+self.selected
  counts={s:0 for s in symbols};latest={}
  for bars in self.history[TradeBar](symbols,253,Resolution.DAILY,data_normalization_mode=DataNormalizationMode.SCALED_RAW):
   for s,b in bars.items():
    if s in counts:
     if b.end_time>self.time:raise ValueError('Future history')
     counts[s]+=1;latest[s]=b.end_time
  if sum(counts[s]==253 for s in self.selected)<5 or not all(counts[s]==253 for s in self.syms):raise ValueError('Insufficient history')
  self.checked=True
  self.debug('QCP|'+json.dumps(dict(kind='free-access',universe_calls=self.calls,valid_fundamentals=self.valid,selected=len(self.selected),etf_full_history=sum(counts[s]==253 for s in self.syms),stock_full_history=sum(counts[s]==253 for s in self.selected),current_history=sum(latest.get(s)==data.bars[self.syms[0]].end_time for s in symbols),orders=0),separators=(',',':')))
  self.quit('Access probe complete; no orders')
 def on_end_of_algorithm(self):
  if not self.checked:raise ValueError('Access not verified')
