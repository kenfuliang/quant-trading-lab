"""Causal completed-history correction and predeclared controls; injected into adapters.
Symbols and engine enums are supplied by the private frozen adapter. No vendor data.
"""
def _refresh_weights(self,data):
    month=(self.time.year,self.time.month)
    if month==self._decision_month:return
    self._decision_month=month;self._selection_events+=1
    if MODE=='spy':
        self._weights={self._syms['SPY']:1.};return
    self._series={s:deque(maxlen=253) for s in self._selected};self._last_bar={}
    history=self.history[TradeBar](self._selected,self.time-timedelta(days=600),self.time,Resolution.DAILY,data_normalization_mode=DataNormalizationMode.SCALED_RAW)
    for bars in history:
        for s,b in bars.items():
            if s not in self._series:continue
            if b.end_time>self.time:
                self._feature_future+=1;raise ValueError('Future feature bar')
            if not math.isfinite(float(b.close)) or b.close<=0:
                self._feature_invalid+=1;raise ValueError('Invalid feature price')
            if s in self._last_bar and b.end_time<=self._last_bar[s]:
                self._feature_unordered+=1;raise ValueError('Unordered or duplicate feature timestamp')
            self._series[s].append(float(b.close));self._last_bar[s]=b.end_time
    self._history_seeded+=len(self._selected)
    self._history_short+=sum(len(v)<253 for v in self._series.values())
    ready=[s for s in self._selected if len(self._series[s])==253 and s in data.bars and self._last_bar[s]==data.bars[s].end_time]
    self._ready_counts.append(len(ready))
    self._feature_hash.update((str(self.time.date())+':'+'|'.join(str(s.id) for s in ready)+'\n').encode())
    if EQUAL_WEIGHT:
        weights={s:1./len(ready) for s in ready}
    else:
        count=3 if MODE=='asset' else 5
        if MODE=='lowvol':selected=sorted(ready,key=lambda s:(return_volatility(list(self._series[s])),str(s.id)))[:count]
        else:selected=sorted(ready,key=lambda s:(-percent_momentum(list(self._series[s])),str(s.id)))[:count]
        weights={s:1./count for s in selected}
    if STRESS:
        self._delay_weights=weights;self._delay_pending=True;self._delay_session=str(data.bars[self._syms['SPY']].time.date())
    else:
        self._weights=weights;self._fund_intent=None

def on_data(self,data):
    if self.is_warming_up or self._syms['SPY'] not in data.bars:return
    self._refresh_weights(data)
    session=str(data.bars[self._syms['SPY']].time.date())
    if STRESS and self._delay_pending and session>self._delay_session:
        self._weights=self._delay_weights;self._fund_intent=None;self._delay_pending=False
    self._fund_accrue(data.bars[self._syms['SPY']].time.date())
    self._funded_rebalance()
    self._audit_record(data)
    self._fund_cash=float(self.portfolio.cash)
