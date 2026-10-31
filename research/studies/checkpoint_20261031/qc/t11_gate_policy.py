"""Project-owned causal observer and cap for the frozen T11 transfer experiment."""
def gate_initialize(self):
    self._gate = GateCore()
    self._gate_counts = dict(green=0, yellow=0, red=0, unassessed=0)
    self._gate_changes = 0
    self._gate_hash = hashlib.sha256()
    self._gate_last = None
    bars = self.history[TradeBar](self._syms['SPY'], datetime(2004,1,2), datetime(2020,1,1), Resolution.DAILY, data_normalization_mode=DataNormalizationMode.RAW)
    self._gate_seed_n = 0
    for bar in bars:
        if bar.time.date() >= date(2020,1,1):
            raise ValueError('Future gate seed')
        self._gate.update(bar.close)
        self._gate_seed_n += 1
    if self._gate_seed_n < 200:
        raise ValueError('Insufficient gate seed')

def gate_observe(self, data):
    session = data.bars[self._syms['SPY']].time.date()
    bars = list(self.history[TradeBar](self._syms['SPY'], 2, Resolution.DAILY, data_normalization_mode=DataNormalizationMode.RAW))
    eligible = [b for b in bars if b.time.date() == session and b.end_time <= self.time]
    if len(eligible) != 1 or (self._gate_last is not None and session <= self._gate_last):
        raise ValueError('Missing, duplicate or future gate close')
    before = self._gate.state
    self._gate.update(eligible[0].close)
    self._gate_changes += int(before != self._gate.state)
    self._gate_counts[self._gate.state] += 1
    self._gate_hash.update(('%s:%.2f\n' % (session.isoformat(), round(float(eligible[0].close),2))).encode())
    self._gate_last = session

def gated_t11_weights(self):
    return {ticker: weight*self._gate.cap for ticker,weight in self._ungated_t11_weights().items() if weight*self._gate.cap > 0}
