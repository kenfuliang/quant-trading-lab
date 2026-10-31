"""Project-owned observation add-on, inserted into a private QC strategy clone.
Original third-party source stays in ignored .local; no trading rule is owned here.
"""

def audit_initialize(self):
    self._audit_curve = []
    self._audit_rejects = self._audit_fills = self._audit_other_fills = 0
    self._audit_max_gross = 0.
    self._audit_min_cash = 10000.
    self._audit_sleeves = {k:{} for k in ('t10','t11','s2','s3')}
    self._audit_sessions = hashlib.sha256()
    self._audit_log_bytes = 0


def audit_record(self, data):
    sym = self._syms['SPY']
    if sym not in data.bars:
        return
    session = str(data.bars[sym].time.date())
    nav = float(self.portfolio.total_portfolio_value)
    if not math.isfinite(nav) or nav <= 0:
        raise ValueError('Nonpositive/nonfinite audit NAV')
    if self._audit_curve and session <= self._audit_curve[-1][0]:
        raise ValueError('Duplicate/unsorted audit session')
    self._audit_curve.append((session,nav))
    self._audit_sessions.update((session+'\n').encode())
    self._audit_min_cash = min(self._audit_min_cash,float(self.portfolio.cash))
    self._audit_max_gross = max(self._audit_max_gross,
        sum(abs(float(self.portfolio[s].holdings_value)) for s in self._syms.values())/nav)
    # Selection diagnostics: intended weights, not executions or sleeve P&L.
    for key in ('t10','t11','s2','s3'):
        weights = getattr(self,'_'+key+'_weights')()
        for symbol,weight in weights.items():
            name=symbol.value
            self._audit_sleeves[key][name]=self._audit_sleeves[key].get(name,0)+1


def audit_order(self, event):
    if event.status == OrderStatus.INVALID:
        self._audit_rejects += 1
    if event.status in (OrderStatus.FILLED,OrderStatus.PARTIALLY_FILLED):
        self._audit_fills += 1
        order=self.transactions.get_order_by_id(event.order_id)
        self._audit_other_fills += int(order.type != OrderType.MARKET_ON_OPEN)


def audit_emit(self, payload):
    line=json.dumps(payload,separators=(',',':'),allow_nan=False)
    self._audit_log_bytes += len(line)+60
    if self._audit_log_bytes > 9300:
        raise ValueError('Declared summary log budget exceeded')
    self.debug(line)


def audit_end(self):
    if not self._audit_curve:
        self._audit_emit(dict(study='qc504-v1',case=AUDIT_CASE,kind='empty'))
        return
    opening=10000.
    anchor=f'{AUDIT_START_YEAR-1}-12-31'
    global_peak=opening
    for year in sorted({d[:4] for d,v in self._audit_curve}):
        rows=[(d,v) for d,v in self._audit_curve if d.startswith(year)]
        result=summarize_path(rows,opening,anchor)
        # Keep long-window diagnostics under the free-tier 10KB log cap.
        keep=('n','end','ret','dd','sharpe','annual_calmar','uw','longest_uw','censored','return_sum','return_square_sum')
        if AUDIT_CASE == 'long':
            keep=('n','end','ret','dd','sharpe','annual_calmar','longest_uw')
        result={k:(round(result[k],10) if isinstance(result[k],float) else result[k]) for k in keep}
        global_uw=0
        for d,v in rows:
            global_peak=max(global_peak,v)
            global_uw+=int(v<global_peak)
        result.update(study='qc504-v1',case=AUDIT_CASE,kind='annual',year=year,global_uw=global_uw)
        self._audit_emit(result)
        opening=rows[-1][1];anchor=rows[-1][0]
    result=summarize_path(self._audit_curve,10000.,f'{AUDIT_START_YEAR-1}-12-31')
    result.update(study='qc504-v1',case=AUDIT_CASE,kind='overall',rejects=self._audit_rejects,
        fills=self._audit_fills,other_fills=self._audit_other_fills,max_gross=self._audit_max_gross,
        min_cash=self._audit_min_cash,fees=float(self.portfolio.total_fees),
        first=self._audit_curve[0][0],last=self._audit_curve[-1][0],calendar_hash=self._audit_sessions.hexdigest())
    self._audit_emit(result)
    assets=[]
    for ticker,sym in self._syms.items():
        h=self.portfolio[sym]
        # Exclude hypothetical exit fees; NetProfit already includes dividends.
        pnl=float(h.net_profit+h.total_close_profit(False))
        if pnl or h.total_fees:
            assets.append([ticker,round(pnl,2),round(float(h.total_fees),2)])
    assets.sort(key=lambda x:x[1],reverse=True)
    residual=float(self.portfolio.total_portfolio_value)-10000.-sum(a[1] for a in assets)
    self._audit_emit(dict(study='qc504-v1',case=AUDIT_CASE,kind='assets',
                         values=assets,residual_usd=residual))
    compact={key:sorted(values.items(),key=lambda x:-x[1])[:5] for key,values in self._audit_sleeves.items()}
    self._audit_emit(dict(study='qc504-v1',case=AUDIT_CASE,kind='selections',top_target_days=compact))
