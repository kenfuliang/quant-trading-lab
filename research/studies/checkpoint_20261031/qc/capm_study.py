"""Build a bounded derivative of the Apache-2.0 LEAN CAPM framework example.

Market paths stay inside QuantConnect. Only aggregate metrics and data-readiness
counts are emitted. The original source remains immutable in the licensed export.
"""
from pathlib import Path
import ast
import hashlib

STUDY = 'capm-spy-v1'
ORIGINAL = Path('research/quantconnect/sources/capm_framework_original.py')

INITIALIZE = '''
def initialize(self):
    self.set_start_date(2016, 1, 1)
    self.set_end_date(2025, 12, 31)
    self.set_cash(300000)
    self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)
    self.settings.free_portfolio_value_percentage = 0.01
    self.add_security_initializer(self._security_setup)
    self.universe_settings.resolution = Resolution.MINUTE
    self._spy = self.add_equity('SPY', Resolution.DAILY if CASE == 'probe' else Resolution.MINUTE).symbol
    self.set_benchmark(self._spy)
    self._rows = []
    self._last_mark = None
    self._cash_date = date(2015, 12, 31)
    self._prior_cash = 300000.0
    self._interest = 0.0
    self._gross_max = 0.0
    self._cash_min = 300000.0
    self._fills = self._rejects = 0
    self._fees = 0.0
    self._notional = 0.0
    self._spy_fills = 0
    self._traded = set()
    self._fee_models = set()
    self._bought = False
    self._probe_years = set()
    self._probe_results = []
    self._seq = 0
    self._log_bytes = 0
    if CASE == 'probe':
        # Construct the exact source model dependencies without attaching an alpha.
        self._probe_model = CapmAlphaRankingUniverseSelectionModel()
        self._probe_models = [ConstantAlphaModel(InsightType.PRICE, InsightDirection.UP, timedelta(1), 0.025, None), EqualWeightingPortfolioConstructionModel(), ImmediateExecutionModel(), MaximumDrawdownPercentPerSecurity(0.01)]
        return
    if CASE == 'capm':
        self.set_universe_selection(CapmAlphaRankingUniverseSelectionModel())
        self.set_alpha(ConstantAlphaModel(InsightType.PRICE, InsightDirection.UP, timedelta(1), 0.025, None))
        self.set_portfolio_construction(EqualWeightingPortfolioConstructionModel())
        self.set_execution(ImmediateExecutionModel())
        self.set_risk_management(MaximumDrawdownPercentPerSecurity(0.01))
'''

METHODS = '''
def _security_setup(self, security):
    security.set_slippage_model(ConstantSlippageModel(0.0025))
    security.set_margin_interest_rate_model(MarginInterestRateModel.NULL)

def on_order_event(self, event):
    self._fees += float(event.order_fee.value.amount)
    if event.status in [OrderStatus.INVALID, OrderStatus.CANCELED]:
        self._rejects += 1
    if event.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
        self._fills += 1
        self._notional += abs(float(event.fill_quantity) * float(event.fill_price))
        self._spy_fills += int(event.symbol == self._spy)
        self._traded.add(str(event.symbol.id))

def on_data(self, data):
    if CASE == 'spy' and not self._bought and data.bars.contains_key(self._spy):
        self.set_holdings(self._spy, 1.0)
        self._bought = True
    if CASE == 'probe':
        if self.time.year not in self._probe_years and data.bars.contains_key(self._spy):
            self._probe_years.add(self.time.year)
            self._probe()
        return
    if not data.bars.contains_key(self._spy):
        return
    close = self.securities[self._spy].exchange.hours.get_next_market_close(self.time.replace(hour=0, minute=0, second=0), False)
    if self.time >= close and self._last_mark != self.time.date():
        self._mark()

def _probe(self):
    model = self._probe_model
    bm = model._get_returns(self, model.benchmark)
    good = short = minute_ok = aligned = 0
    bh = self.history([model.benchmark], 21, Resolution.DAILY)
    expected = list(bh.index.get_level_values(-1))
    issues = []
    for symbol in model._symbols:
        h = self.history([symbol], 21, Resolution.DAILY)
        m = self.history([symbol], 1, Resolution.MINUTE)
        r = model._get_returns(self, symbol)
        if not m.empty:
            minute_ok += 1
        if h.empty or r is None:
            issues.append([symbol.value, 'empty'])
            continue
        if len(r) != len(bm):
            short += 1
            issues.append([symbol.value, 'short', len(r)])
            continue
        dates = list(h.index.get_level_values(-1))
        if dates == expected:
            aligned += 1
        else:
            issues.append([symbol.value, 'calendar-mismatch'])
        if dates and dates[-1] > pd.Timestamp(self.time):
            raise ValueError('Future history')
        if not all(math.isfinite(float(x)) for x in r):
            raise ValueError('Nonfinite source features')
        # Validate the actual source regression in its original direction.
        np.linalg.lstsq(np.vstack([r, np.ones(len(bm))]).T, bm, rcond=None)
        good += 1
    result = dict(year=self.time.year, ready=good, aligned=aligned, short=short, minute=minute_ok, issues=issues)
    self._probe_results.append(result)

def _mark(self):
    session = self.time.date()
    elapsed = (session - self._cash_date).days
    charge = max(-self._prior_cash, 0.0) * 0.06 * elapsed / 360.0
    before = float(self.portfolio.total_portfolio_value)
    if charge:
        self.portfolio.cash_book['USD'].add_amount(-charge)
    nav = float(self.portfolio.total_portfolio_value)
    if abs(before - nav - charge) > 0.01:
        raise ValueError('Financing debit did not reconcile')
    self._interest += charge
    self._prior_cash = float(self.portfolio.cash_book['USD'].amount)
    self._cash_min = min(self._cash_min, self._prior_cash)
    self._cash_date = self._last_mark = session
    if not math.isfinite(nav) or nav <= 0:
        raise ValueError('Invalid NAV')
    gross = sum(abs(float(h.holdings_value)) for h in self.portfolio.values()) / nav
    self._gross_max = max(self._gross_max, gross)
    for s in self.securities.values():
        if s.invested:
            name = type(s.fee_model).__name__
            if name != 'InteractiveBrokersFeeModel':
                raise ValueError('Unexpected fee model: ' + name)
            self._fee_models.add(name)
    self._rows.append((session.isoformat(), nav))

def on_end_of_algorithm(self):
    if CASE == 'probe':
        payload = dict(study=STUDY, case=CASE, kind='probe', years=self._probe_results, universe_count=len(self._probe_model._symbols), numpy=np.__version__, pandas=pd.__version__, models=[type(m).__name__ for m in self._probe_models], fills=self._fills, rejects=self._rejects)
        self._emit(payload)
        return
    if not self._rows:
        raise ValueError('No closing marks')
    opening, anchor = 300000.0, '2015-12-31'
    for year in range(2016, 2026):
        rows = [r for r in self._rows if r[0].startswith(str(year))]
        if not rows:
            raise ValueError('Missing annual observations')
        metric = summarize_path(rows, opening, anchor)
        self._emit(dict(study=STUDY, case=CASE, kind='annual', year=year, metrics=self._round(metric)))
        opening, anchor = rows[-1][1], rows[-1][0]
    metric = summarize_path(self._rows, 300000.0, '2015-12-31')
    native_pnl = sum(float(h.net_profit) + float(h.total_close_profit(False)) for h in self.portfolio.values())
    active_only_residual = float(self.portfolio.total_portfolio_value) - 300000.0 - native_pnl + self._interest
    # TotalNetProfit includes removed securities; Values does not. Current mark
    # unrealized P&L avoids a hypothetical closing bid/ask or liquidation fee.
    all_realized_net = float(self.portfolio.total_net_profit)
    mark_unrealized = sum(float(h.holdings_value) - float(h.holdings_cost) for h in self.portfolio.values())
    residual = float(self.portfolio.total_portfolio_value) - 300000.0 - all_realized_net - mark_unrealized + self._interest
    self._emit(dict(study=STUDY, case=CASE, kind='full', metrics=self._round(metric), audit=dict(first=self._rows[0][0], last=self._rows[-1][0], calendar_hash=hashlib.sha256('|'.join(r[0] for r in self._rows).encode()).hexdigest(), fills=self._fills, rejects=self._rejects, fees=round(self._fees, 6), interest=round(self._interest, 6), min_cash=round(self._cash_min, 6), max_gross=round(self._gross_max, 8), fee_models=sorted(self._fee_models), native_fee_residual=round(float(self.portfolio.total_fees)-self._fees, 6), active_only_residual=round(active_only_residual, 6), fill_notional_usd=round(self._notional, 2), spy_fills=self._spy_fills, traded_symbols=len(self._traded), native_book_residual=round(residual, 6), last_mark_residual=round(float(self.portfolio.total_portfolio_value)-self._rows[-1][1], 6), pending=len(self.transactions.get_open_orders()))))

def _round(self, values):
    return {k: round(v, 12) if isinstance(v, float) else v for k, v in values.items()}

def _emit(self, payload):
    line = json.dumps(payload, separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(line.encode()).hexdigest()[:12]
    chunks = [line[i:i+145] for i in range(0, len(line), 145)]
    for i, chunk in enumerate(chunks):
        out = f'CAP|{CASE}|{self._seq}|{i}|{len(chunks)}|{digest}|{chunk}'
        self._log_bytes += len(out.encode())
        if self._log_bytes > 9500:
            raise ValueError('Aggregate export log budget exceeded')
        self.debug(out)
    self._seq += 1
'''


def build_source(case: str) -> str:
    if case not in {'probe', 'capm', 'spy'}:
        raise ValueError('Unknown study case')
    original = ORIGINAL.read_text()
    tree = ast.parse(original)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CapmAlphaRankingFrameworkAlgorithm')
    cls.body = [ast.parse(INITIALIZE).body[0], *ast.parse(METHODS).body]
    metrics = Path('research/quantconnect/sector_metrics.py').read_text()
    notice = original[:original.index('from AlgorithmImports')]
    header = ("# Modified for capm-spy-v1: dates/capital/common costs, order-free dependency probe,\n"
              "# closing aggregate metrics and accounting audits. Original ranking/framework rules retained.\n"
              "# Not the exact hosted tutorial implementation; viewed development history.\n")
    return notice + header + f"STUDY = {STUDY!r}\nCASE = {case!r}\nimport hashlib\nimport json\n" + metrics + '\n' + ast.unparse(tree) + '\n'


def write_sources(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for case in ['probe', 'capm', 'spy']:
        source = build_source(case)
        ast.parse(source)
        if len(source) >= 32000:
            raise ValueError('Cloud editor source limit')
        path = root / f'{case}-source.py'
        if path.exists() and path.read_text() != source:
            raise ValueError('Preserve frozen source before regenerating')
        path.write_text(source)
        hashes[case] = hashlib.sha256(source.encode()).hexdigest()
    return hashes
