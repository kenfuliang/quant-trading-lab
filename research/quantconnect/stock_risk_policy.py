"""Fixed stock-momentum risk overlay and derived evidence; no parameter search.

Functions are injected into a private QC adapter. Sector cap is a target cap,
not an intraday or continuous mark-to-market guarantee. Residual stays cash.
"""
def sector_weights(weights, sectors, limit=0.4):
    totals = {}
    for symbol, weight in weights.items():
        sector = sectors.get(symbol, 0)
        totals[sector] = totals.get(sector, 0.) + weight
    return {s: w * min(1., limit / totals[sectors[s]])
            for s, w in weights.items() if sectors.get(s, 0) > 0}


def _risk_initialize(self):
    self._risk_records = []
    self._risk_months = []
    self._risk_symbols = []
    self._risk_symbol_index = {}
    self._risk_sectors = {}
    self._risk_sector_weights = {}
    self._risk_previous_month = None
    self._risk_gross_sum = self._risk_sector_peak = 0.
    self._risk_missing_sector = 0
    self._gate_initialize()


def _risk_index(self, symbol):
    sid = str(symbol.id)
    code = self._risk_sectors.get(symbol, 0)
    key = (sid, code)
    if key not in self._risk_symbol_index:
        self._risk_symbol_index[key] = len(self._risk_symbols)
        self._risk_symbols.append([sid, code])
    return self._risk_symbol_index[key]


def _risk_monthly(self, data):
    month = self._decision_month
    if month == self._risk_previous_month:
        return
    self._risk_previous_month = month
    self._risk_sector_weights = sector_weights(self._weights, self._risk_sectors) if APPLY_SECTOR else dict(self._weights)
    self._risk_missing_sector += sum(self._risk_sectors.get(s, 0) == 0 for s in self._weights) if MODE != 'spy' else 0
    # Rank is array order; base target=.18 each (SPY=.90). Sector target follows
    # the declared proportional rule and gate target follows the recorded color.
    rows = [self._risk_index(s) for s in self._weights]
    self._risk_months.append([int(self.time.strftime('%Y%m%d')),
                              ('unassessed','green','yellow','red').index(self._gate.state),
                              self._ready_counts[-1] if self._ready_counts else 0, rows])


def _t10_weights(self):
    cap = self._gate.cap if APPLY_GATE else 1.
    return {s: w * cap for s, w in self._risk_sector_weights.items() if w * cap > 0}


def _risk_observe_exposure(self):
    nav = float(self.portfolio.total_portfolio_value)
    by_sector = {}
    gross = 0.
    for s in self._syms.values():
        value = abs(float(self.portfolio[s].holdings_value)) / nav
        gross += value
        code = self._risk_sectors.get(s, 0)
        by_sector[code] = by_sector.get(code, 0.) + value
    self._risk_gross_sum += gross
    self._risk_sector_peak = max([self._risk_sector_peak] + list(by_sector.values()))


def _risk_finish(self):
    # Readable JSON with documented positional schemas; no encoding/compression.
    # No OHLCV, fundamentals, raw signal history or vendor dataset is exported.
    full = next(r for r in self._risk_records if r['kind']=='overall')
    annual_keys = ['year','n','end','ret','dd','sharpe','annual_calmar','uw','longest_uw','censored','global_uw','financing_usd']
    assets = next(r for r in self._risk_records if r['kind']=='assets')
    contributions = []
    for sid, pnl, fees in assets['values']:
        if sid == 'SPY':
            symbol = self._syms['SPY']
        else:
            symbol = self._syms[sid]
        contributions.append([self._risk_index(symbol), round(pnl*100), round(fees*100)])
    # Redundant moment fields can be recomputed from engine NAV but are not
    # exported under this quota; annual compounding and PnL checks remain available.
    full_keys = ['n','end','ret','cagr','dd','sharpe','calmar','uw','uw_fraction','longest_uw','longest_uw_days','censored','rejects','fills','other_fills','max_gross','fees','calendar_hash','feature_sha256','feature_future','feature_invalid','feature_unordered','selection_events','history_short','min_ready','membership_sha256','financing_usd','pending_orders','funding_debit_error']
    package = dict(study='stock-risk-v1', case=AUDIT_CASE,
                   full={k:round(full[k],10) if isinstance(full[k],float) else full[k] for k in full_keys},
                   annual_keys=annual_keys,
                   annual=[[r[k] for k in annual_keys] for r in self._risk_records if r['kind']=='annual'],
                   contributions=contributions, residual_usd=round(assets['residual_usd'],6),
                   symbols=self._risk_symbols, months=self._risk_months,
                   gate_counts=self._gate_counts, gate_changes=self._gate_changes,
                   gate_input_sha256=self._gate_hash.hexdigest(), gate_seed_n=self._gate_seed_n,
                   average_gross=round(self._risk_gross_sum / len(self._audit_curve),8),
                   peak_sector_gross=round(self._risk_sector_peak,8),
                   selected_unknown_sector=self._risk_missing_sector)
    plain = json.dumps(package, separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(plain.encode()).hexdigest()[:12]
    chunks = [plain[i:i+130] for i in range(0, len(plain), 130)]
    messages = ['RSG|%s|%s|%s|%s|%s' % (AUDIT_CASE, i, len(chunks), digest, c)
                for i, c in enumerate(chunks)]
    if sum(len(m) for m in messages) > 9000:
        raise ValueError('Derived evidence exceeds frozen free-log budget')
    for message in messages:
        self.debug(message)
