"""Order-free investigation of historical classification availability."""
def _sector_probe_initialize(self):
    self._sector_details = {}
    self._sector_probe_rows = []
    self._sector_probe_month = None
    self._sector_probe_decisions = 0


def _sector_probe_capture(self, fundamentals):
    for f in fundamentals:
        a = f.asset_classification
        self._sector_details[f.symbol] = [f.symbol.value,
            int(a.morningstar_sector_code), int(a.morningstar_industry_group_code),
            int(a.morningstar_industry_code), int(a.sic), str(f.end_time)]


def on_data(self, data):
    if self.is_warming_up or self._syms['SPY'] not in data.bars:
        return
    self._refresh_weights(data)
    if self._decision_month == self._sector_probe_month:
        return
    self._sector_probe_month = self._decision_month
    self._sector_probe_decisions += 1
    for symbol in self._weights:
        detail = self._sector_details[symbol]
        if detail[1] == 0:
            actual = self.securities[symbol].fundamentals.asset_classification
            self._sector_probe_rows.append([str(self.time.date()),str(symbol.id)] + detail +
                [int(actual.morningstar_sector_code),int(actual.morningstar_industry_group_code),int(actual.morningstar_industry_code)])


def _audit_end(self):
    result = dict(study='sector-matched-v1',case='probe',decisions=self._sector_probe_decisions,
                  rows=self._sector_probe_rows, orders=len(self.transactions.get_orders()),
                  nav=float(self.portfolio.total_portfolio_value),
                  feature_sha256=self._feature_hash.hexdigest(),
                  membership_sha256=self._membership_hash.hexdigest(),
                  future=self._feature_future,invalid=self._feature_invalid,
                  unordered=self._feature_unordered)
    plain = json.dumps(result,separators=(',',':'),allow_nan=False)
    digest = hashlib.sha256(plain.encode()).hexdigest()[:12]
    chunks = [plain[i:i+130] for i in range(0,len(plain),130)]
    messages = ['SCM|probe|%d|%d|%s|%s' % (i,len(chunks),digest,s) for i,s in enumerate(chunks)]
    if sum(map(len,messages)) > 9000:
        raise ValueError('Probe log quota exceeded')
    for message in messages:self.debug(message)
