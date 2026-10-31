"""Order-free bounded validation of explicit calendar-span feature requests."""
def diag_initialize(self):
    self._diag_windows=0;self._diag_rows=[];self._diag_short=[]
    self._diag_future=self._diag_invalid=self._diag_unordered=0
    self._diag_etf=None

def diag_window(self,symbols,data):
    check={s:[] for s in symbols}
    for bars in self.history[TradeBar](symbols,self.time-timedelta(days=600),self.time,Resolution.DAILY,data_normalization_mode=DataNormalizationMode.SCALED_RAW):
        for s,b in bars.items():
            if s in check:check[s].append(b)
    ready=0
    for s,bars in check.items():
        self._diag_future+=sum(b.end_time>self.time for b in bars)
        self._diag_invalid+=sum(not math.isfinite(float(b.close)) or b.close<=0 for b in bars)
        self._diag_unordered+=sum(a.end_time>=b.end_time for a,b in zip(bars,bars[1:]))
        ok=len(bars)>=253 and s in data.bars and bars[-1].end_time==data.bars[s].end_time
        ready+=int(ok)
        if not ok:self._diag_short.append([str(data.bars[self._syms['SPY']].time.date()),s.value,len(bars),str(bars[0].time) if bars else None,str(bars[-1].end_time) if bars else None,s in data.bars])
    return ready

def diag_record(self,data):
    self._diag_windows+=1
    spy=data.bars[self._syms['SPY']]
    ready=self._diag_window(self._selected,data)
    self._diag_rows.append([str(spy.time.date()),len(self._selected),self._ready_counts[-1],ready])
    if str(spy.time.date())=='2023-07-03':
        etfs=[self._syms[t] for t in ['SPY','EFA','BND','VNQ','GSG']]
        self._diag_etf=dict(session=str(spy.time.date()),selected=5,wide_ready=self._diag_window(etfs,data))

def diag_end(self):
    if self._diag_windows!=72:raise ValueError('Missing diagnostic windows')
    if list(self.transactions.get_orders()):raise ValueError('Diagnostic submitted an order')
    self._audit_emit(dict(study='selection-completion-v1',case=AUDIT_CASE,kind='readiness',windows=self._diag_windows,counts=self._diag_rows,remaining_ineligible=self._diag_short,early_close_etfs=self._diag_etf,future=self._diag_future,invalid=self._diag_invalid,unordered=self._diag_unordered,orders=0))
