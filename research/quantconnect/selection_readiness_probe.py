"""Order-free observer injected into frozen private selection adapters.
Exports aggregate coverage and anomaly metadata, never price/fundamental values.
"""
def diag_initialize(self):
    self._diag_windows=0;self._diag_counts=[];self._diag_anomalies={}
    self._diag_future=self._diag_invalid=self._diag_unordered=0
    self._diag_first=None

def diag_record(self,data):
    self._diag_windows+=1
    spy=data.bars[self._syms['SPY']]
    original_counts=[len(self._series[s]) for s in self._selected]
    original_ready=self._ready_counts[-1]
    self._diag_counts.append([str(spy.time.date()),len(self._selected),original_ready,min(original_counts) if original_counts else 0])
    # Re-query exactly the same request, retaining timestamps to validate causality.
    check={s:[] for s in self._selected}
    for bars in self.history[TradeBar](self._selected,253,Resolution.DAILY,data_normalization_mode=DataNormalizationMode.SCALED_RAW):
        for s,b in bars.items():
            if s in check:check[s].append(b)
    for s,bars in check.items():
        self._diag_future+=sum(b.end_time>self.time for b in bars)
        self._diag_invalid+=sum(not math.isfinite(float(b.close)) or b.close<=0 for b in bars)
        self._diag_unordered+=sum(a.end_time>=b.end_time for a,b in zip(bars,bars[1:]))
        old=len(self._series[s])
        if old<253 or s not in data.bars or self._last_bar.get(s)!=data.bars[s].end_time:
            single=list(self.history[TradeBar](s,253,Resolution.DAILY,data_normalization_mode=DataNormalizationMode.SCALED_RAW))
            item=dict(session=str(spy.time.date()),now=str(self.time),symbol=s.value,old=old,repeat=len(bars),single=len(single),first=str(single[0].time) if single else None,last=str(single[-1].end_time) if single else None,in_slice=s in data.bars,bar_end=str(data.bars[s].end_time) if s in data.bars else None,spy_end=str(spy.end_time),fill_forward=bool(data.bars[s].is_fill_forward) if s in data.bars else None,has_data=bool(self.securities[s].has_data))
            key=(item['session'],item['old'],item['repeat'],item['single'],item['first'],item['last'],item['in_slice'],item['bar_end'],item['spy_end'])
            if key in self._diag_anomalies:self._diag_anomalies[key]['count']+=1
            else:self._diag_anomalies[key]=dict(item,count=1)
    if self._diag_first is None:
        self._diag_first=dict(now=str(self.time),spy_start=str(spy.time),spy_end=str(spy.end_time),selected=len(self._selected),counts=original_counts,ready=original_ready)

def diag_end(self):
    if self._diag_windows!=72:raise ValueError('Missing diagnostic windows')
    if list(self.transactions.get_orders()):raise ValueError('Diagnostic submitted an order')
    self._audit_emit(dict(study='selection-completion-v1',case=AUDIT_CASE,kind='readiness',windows=self._diag_windows,first=self._diag_first,counts=self._diag_counts,anomalies=list(self._diag_anomalies.values()),future=self._diag_future,invalid=self._diag_invalid,unordered=self._diag_unordered,orders=0))
