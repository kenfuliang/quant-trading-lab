"""Causal, explicitly adapted NVDA/AMD pairs study; original plot script is not executed."""
from pathlib import Path
from datetime import date
import ast
import hashlib
import inspect
import json
import math
import numpy as np
from research.studies.checkpoint_20261031.qc.capm_study import build_source as account_source
from research.studies.checkpoint_20261031.capm_review import _audit_ratios

STUDY = 'stock-pairs-spy-v1'
CASES = ['probe', 'spy', 'pairhold', 'pairs']
SOURCE = Path(__file__).parent/'quantconnect/sources/stock_pairs_original.py'
SOURCE_SHA = 'd3088cbee0bc494513075d8f79ec4a9e940e17f432b9e2a86977f639a1e9d471'


def fit_pair(x, y, current_x, current_y, coint_test):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) != 250 or len(y) != 250 or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)) or np.min(x) <= 0 or np.min(y) <= 0 or not all(math.isfinite(v) and v > 0 for v in [current_x, current_y]):
        raise ValueError('250 aligned positive prior closes required')
    design = np.column_stack([np.ones(len(x)), x])
    if np.linalg.matrix_rank(design) != 2:
        raise ValueError('Degenerate price regression')
    alpha, beta = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y - alpha - beta*x
    sigma = float(np.std(residual, ddof=1))
    if sigma <= 1e-12:
        raise ValueError('Degenerate residual dispersion')
    # A cointegration-specific distribution is required after estimating the regression.
    _, pvalue, _ = coint_test(y, x, trend='c', maxlag=5, autolag='aic')
    correction = float(np.linalg.lstsq(np.column_stack([np.ones(249), np.diff(x), residual[:-1]]), np.diff(y), rcond=None)[0][-1])
    z = float((current_y-alpha-beta*current_x-float(np.mean(residual)))/sigma)
    if not all(math.isfinite(v) for v in [alpha, beta, sigma, pvalue, correction, z]):
        raise ValueError('Nonfinite pair fit')
    return dict(alpha=float(alpha), beta=float(beta), sigma=sigma, p=float(pvalue), correction=correction, z=z, eligible=bool(pvalue < .05 and beta > 0 and correction < 0))


def next_direction(model, previous):
    if previous not in [-1, 0, 1]:
        raise ValueError('Direction state')
    if not model['eligible']:
        return 0
    z = model['z']
    if previous == 1:
        return 0 if z <= 0 else 1
    if previous == -1:
        return 0 if z >= 0 else -1
    return 1 if z >= 1 else -1 if z <= -1 else 0


def pair_weights(model, direction, price_x, price_y):
    if direction == 0:
        return [0., 0.]
    if direction not in [-1, 1] or model['beta'] <= 0 or min(price_x, price_y) <= 0:
        raise ValueError('Invalid hedge sizing')
    hedge_value = model['beta']*price_x
    denominator = hedge_value+price_y
    return [.98*direction*hedge_value/denominator, -.98*direction*price_y/denominator]


METHODS = '''
def _pair_inputs(self):
    # SCALED_RAW uses only actions known before the algorithm's current time.
    history=self.history(self._symbols,timedelta(days=600),Resolution.DAILY,data_normalization_mode=DataNormalizationMode.SCALED_RAW)
    values=[]
    for symbol in self._symbols:
        series=history.loc[symbol]['close'].sort_index()
        rows=[(t.date(),float(v)) for t,v in series.items() if t.date()<self.time.date()]
        if len({t for t,v in rows})!=len(rows):raise ValueError('Duplicate daily history')
        rows=rows[-250:]
        if len(rows)!=250 or any(not math.isfinite(v) or v<=0 for t,v in rows):raise ValueError('Short/invalid prior history '+str(symbol)+':'+str(len(rows)))
        values.append(rows)
    days=[t for t,v in values[0]]
    if any([t for t,v in r]!=days for r in values):raise ValueError('Mismatched SPY/pair history dates')
    if days[-1]>=self.time.date():raise ValueError('Current/future observation in training')
    return [v for t,v in values[1]],[v for t,v in values[2]],days

def _decision(self,data):
    x,y,days=self._pair_inputs()
    current_x=float(data.bars[self._a].close)
    current_y=float(data.bars[self._b].close)
    model=fit_pair(x,y,current_x,current_y,coint)
    self._ready_days+=1
    self._eligible_days+=int(model['eligible'])
    self._fit_hash.update((self.time.date().isoformat()+'|'+days[0].isoformat()+'|'+days[-1].isoformat()+'|'+','.join(format(model[k],'.12g') for k in ['alpha','beta','sigma','p','correction','z'])+';').encode())
    if self.time.year not in self._probe_years:
        self._probe_years.add(self.time.year)
        self._probe_results.append(dict(year=self.time.year,prior_count=len(x),prior_last=days[-1].isoformat(),decision=self.time.date().isoformat(),p=round(model['p'],8),history_aligned=True))
    if CASE=='probe':return
    if CASE=='pairs':
        self._direction=next_direction(model,self._direction)
        weights=pair_weights(model,self._direction,current_x,current_y)
        self._pending_weights=[0.]+weights
    elif not self._bought:
        self._pending_weights=[.98,0.,0.] if CASE=='spy' else [0.,.49,.49]
    else:return
    self._signal_day=self.time.date()

def on_data(self,data):
    if self._prior_time is not None:
        elapsed=(self.time-self._prior_time).total_seconds()
        charge=self._prior_short_notional*.03*elapsed/(365*86400)
        if charge:
            self.portfolio.cash_book['USD'].add_amount(-charge)
            self._borrow+=charge
    for event in data.splits.values():
        if event.symbol in self._symbols and event.type==SplitType.SPLIT_OCCURRED:
            self._split_counts[str(event.symbol.value)]+=1
    for event in data.dividends.values():
        if event.symbol in self._symbols:self._dividend_counts[str(event.symbol.value)]+=1
    if data.bars.contains_key(self._spy):
        if not all(data.bars.contains_key(s) for s in self._symbols):raise ValueError('Missing synchronized minute bar')
        for s in self._symbols:
            bar=data.bars[s]
            if not all(math.isfinite(float(v)) and float(v)>0 for v in [bar.open,bar.high,bar.low,bar.close]) or bar.high<max(bar.open,bar.low,bar.close) or bar.low>min(bar.open,bar.close):raise ValueError('Invalid raw minute OHLC')
        day=self.time.date()
        if CASE!='probe' and self._pending_weights is not None and day>self._signal_day:
            opening=self.securities[self._spy].exchange.hours.get_next_market_open(self.time.replace(hour=0,minute=0,second=0),False)
            if self.time>=opening+timedelta(minutes=2):
                if self.time!=opening+timedelta(minutes=2):raise ValueError('Missed next-session execution')
                if self.transactions.get_open_orders():raise ValueError('Prior pending broker order')
                self.set_holdings([PortfolioTarget(s,w) for s,w in zip(self._symbols,self._pending_weights)])
                self._executions+=1
                self._pending_weights=None
                self._bought=True
        nav=float(self.portfolio.total_portfolio_value)
        if not math.isfinite(nav) or nav<=0:raise ValueError('Invalid NAV')
        gross=sum(abs(float(self.portfolio[s].holdings_value)) for s in self._symbols)/nav
        net=sum(float(self.portfolio[s].holdings_value) for s in self._symbols)/nav
        self._minute_n+=1
        self._minute_gross_sum+=gross
        self._minute_net_sum+=net
        self._minute_gross_max=max(self._minute_gross_max,gross)
        self._minute_peak=max(self._minute_peak,nav)
        self._minute_dd=min(self._minute_dd,nav/self._minute_peak-1)
        self._short_minutes+=int(any(self.portfolio[s].quantity<0 for s in self._symbols))
        close=self.securities[self._spy].exchange.hours.get_next_market_close(self.time.replace(hour=0,minute=0,second=0),False)
        if self.time>=close and self._last_decision!=day:
            self._decision(data)
            self._last_decision=day
            if CASE!='probe':
                self._mark()
                realized=float(self.portfolio.total_net_profit)
                unrealized=sum(float(h.holdings_value)-float(h.holdings_cost) for h in self.portfolio.values())
                residual=float(self.portfolio.total_portfolio_value)-300000-realized-unrealized+self._interest+self._borrow
                self._book_max=max(self._book_max,abs(residual))
                if abs(residual)>2:raise ValueError('Daily native accounting mismatch')
    self._prior_short_notional=sum(max(-float(self.portfolio[s].holdings_value),0) for s in self._symbols)
    self._prior_time=self.time
'''


def build_source(case):
    if case not in CASES or hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SOURCE_SHA:
        raise ValueError('Unknown case')
    text=account_source('spy').replace("STUDY = 'capm-spy-v1'",f"STUDY = {STUDY!r}").replace("CASE = 'spy'",f"CASE = {case!r}\nSOURCE_TOKEN = 'TOKEN_PLACEHOLDER'")
    text=text.replace('ConstantSlippageModel(0.0025)','ConstantSlippageModel(0.0005)').replace("f'CAP|{CASE}|","f'PRS|{CASE}|")
    text=text.replace('self._fills += 1',"self._fee_models.add(type(self.securities[event.symbol].fee_model).__name__)\n            self._fills += 1")
    text=text.replace(' + self._interest\n',' + self._interest + self._borrow\n')
    fields="source_token=SOURCE_TOKEN,fit_hash=self._fit_hash.hexdigest(),ready_days=self._ready_days,eligible_days=self._eligible_days,borrow_usd=round(self._borrow,6),minute_observations=self._minute_n,minute_mean_gross=round(self._minute_gross_sum/self._minute_n,10),minute_mean_net=round(self._minute_net_sum/self._minute_n,10),minute_max_gross=round(self._minute_gross_max,10),minute_dd=round(self._minute_dd,12),short_minutes=self._short_minutes,daily_book_max=round(self._book_max,6),executions=self._executions,split_counts=self._split_counts,dividend_counts=self._dividend_counts,native_dividends=round(sum(float(h.total_dividends) for h in self.portfolio.values()),6),"
    text=text.replace('audit=dict(first=','audit=dict('+fields+'first=')
    tree=ast.parse(text)
    tree.body=[n for n in tree.body if not (isinstance(n,ast.ClassDef) and n.name=='CapmAlphaRankingUniverseSelectionModel')]
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef));cls.name='StockPairsStudyAlgorithm'
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
    init.body=[n for n in init.body if not isinstance(n,ast.If)]
    for n in ast.walk(init):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_equity':
            n.args=[ast.Constant('SPY'),ast.Attribute(value=ast.Name(id='Resolution',ctx=ast.Load()),attr='MINUTE',ctx=ast.Load())]
            n.keywords.append(ast.keyword(arg='data_normalization_mode',value=ast.Attribute(value=ast.Name(id='DataNormalizationMode',ctx=ast.Load()),attr='RAW',ctx=ast.Load())))
    init.body+=ast.parse('''
self.settings.daily_precise_end_time=True
self._a=self.add_equity('NVDA',Resolution.MINUTE,data_normalization_mode=DataNormalizationMode.RAW).symbol
self._b=self.add_equity('AMD',Resolution.MINUTE,data_normalization_mode=DataNormalizationMode.RAW).symbol
self._symbols=[self._spy,self._a,self._b]
self._borrow=0.
self._prior_time=None
self._prior_short_notional=0.
self._ready_days=self._eligible_days=0
self._fit_hash=hashlib.sha256()
self._last_decision=None
self._pending_weights=None
self._signal_day=None
self._direction=0
self._minute_n=0
self._minute_gross_sum=self._minute_net_sum=0.
self._minute_gross_max=0.
self._minute_peak=300000.
self._minute_dd=0.
self._book_max=0.
self._short_minutes=self._executions=0
self._split_counts={str(s.value):0 for s in self._symbols}
self._dividend_counts={str(s.value):0 for s in self._symbols}
self.debug(f'PRS_START|{CASE}|{SOURCE_TOKEN}|statsmodels={statsmodels.__version__}')
''').body
    methods=METHODS if case=='probe' else METHODS.replace('self.time-self._prior_time','self.utc_time-self._prior_time').replace('self._prior_time=self.time','self._prior_time=self.utc_time')
    cls.body=[n for n in cls.body if not (isinstance(n,ast.FunctionDef) and n.name in ['on_data','_probe'])]+ast.parse(methods).body
    end=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='on_end_of_algorithm')
    end.body=ast.parse("if self._ready_days!=2514:\n    self.debug('PRS_INCOMPLETE|'+CASE+'|'+str(self._ready_days))\n    return\nif CASE=='probe':\n    self._emit(dict(study=STUDY,case=CASE,kind='probe',source_token=SOURCE_TOKEN,ready_days=self._ready_days,fit_hash=self._fit_hash.hexdigest(),years=self._probe_results,fills=self._fills,rejects=self._rejects,statsmodels=statsmodels.__version__,numpy=np.__version__,pandas=pd.__version__,normalization=sorted(set(str(c.data_normalization_mode) for c in self.subscription_manager.subscriptions if c.symbol in self._symbols)),models=sorted(set(type(self.securities[s].fee_model).__name__ for s in self._symbols)),split_counts=self._split_counts,dividend_counts=self._dividend_counts))\n    return").body+end.body[2:]
    tree.body=ast.parse('import statsmodels\nfrom statsmodels.tsa.stattools import coint').body+tree.body
    tree.body+=ast.parse('\n\n'.join(inspect.getsource(f) for f in [fit_pair,next_direction,pair_weights])).body
    ast.fix_missing_locations(tree)
    notice='# Causal NVDA/AMD mechanism adaptation of Apache-2.0 je-suis-tm/quant-trading example.\n# Original stock_pairs_original.py and LICENSE-JeSuisTM.txt remain unchanged, never imported.\n# Repairs: causal sizing, proper cointegration p-value, dimensionless z bands, state persistence, raw actions/PIT history.\n'
    rendered=notice+ast.unparse(tree)+'\n';token=hashlib.sha256(rendered.encode()).hexdigest()[:16];rendered=rendered.replace('TOKEN_PLACEHOLDER',token)
    if len(rendered)>=32000:
        raise ValueError('Cloud source size')
    return rendered


def decode_fragments(lines,case):
    groups={}
    for line in lines:
        if 'PRS|' not in line:continue
        _,actual,seq,i,n,digest,chunk=line[line.index('PRS|'):].split('|',6)
        if actual!=case:continue
        parts=groups.setdefault((int(seq),int(n),digest),{})
        if int(i) in parts and parts[int(i)]!=chunk:raise ValueError('Conflicting packet')
        parts[int(i)]=chunk
    if not groups:raise ValueError('Missing packets')
    rows=[]
    for (_,n,digest),parts in sorted(groups.items()):
        if set(parts)!=set(range(n)):raise ValueError('Incomplete packets')
        raw=''.join(parts[i] for i in range(n))
        if hashlib.sha256(raw.encode()).hexdigest()[:12]!=digest:raise ValueError('Packet checksum')
        r=json.loads(raw)
        if r['case']!=case or r['study']!=STUDY:raise ValueError('Packet identity')
        rows.append(r)
    return rows


def audit_records(rows,case):
    token=next(n.value.value for n in ast.parse(build_source(case)).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='SOURCE_TOKEN')
    if case=='probe':
        if len(rows)!=1:raise ValueError('Probe packet count')
        a=rows[0]
        if a['source_token']!=token or a['ready_days']!=2514 or a['fills'] or a['rejects'] or [x.upper() for x in a['normalization']]!=['RAW'] or a['models']!=['InteractiveBrokersFeeModel'] or sorted(x['year'] for x in a['years'])!=list(range(2016,2026)) or any(x['prior_count']!=250 or not x['history_aligned'] or x['prior_last']>=x['decision'] for x in a['years']):raise ValueError('Input/dependency gate failed')
    else:
        full=next(r for r in rows if r['kind']=='full');annual=[r for r in rows if r['kind']=='annual'];m,a=full['metrics'],full['audit']
        if len(rows)!=11 or sorted(r['year'] for r in annual)!=list(range(2016,2026)) or a['source_token']!=token or a['first']!='2016-01-04' or a['last']!='2025-12-31' or m['n']!=2514 or a['ready_days']!=2514 or a['minute_observations']!=976680:raise ValueError('Financial calendar/input gate')
        if a['rejects'] or a['pending'] or abs(a['native_book_residual'])>2 or a['daily_book_max']>2 or abs(a['native_fee_residual'])>.01 or abs(a['last_mark_residual'])>.01 or (a['fills'] and a['fee_models']!=['InteractiveBrokersFeeModel']):raise ValueError('Native accounting/execution gate')
        if case!='pairs' and (a['short_minutes'] or a['borrow_usd']):raise ValueError('Unexpected short exposure')
        if abs(m['end']/300000-1-m['ret'])>1e-9 or abs((m['end']/300000)**(365.25/(date(2025,12,31)-date(2015,12,31)).days)-1-m['cagr'])>1e-9:raise ValueError('Capital/CAGR identity')
        factor=1
        for r in annual:factor*=1+r['metrics']['ret'];_audit_ratios(r['metrics'],True)
        _audit_ratios(m,False)
        if abs(factor-1-m['ret'])>1e-8 or sum(r['metrics']['n'] for r in annual)!=2514:raise ValueError('Annual compounding/count')
    if a['split_counts']['NVDA']<2 or a['dividend_counts']['SPY']<30 or a['dividend_counts']['NVDA']<30:raise ValueError('Corporate-action feed gate')
    return dict(passed=True,case=case,fit_hash=a['fit_hash'],ready_days=a['ready_days'])
