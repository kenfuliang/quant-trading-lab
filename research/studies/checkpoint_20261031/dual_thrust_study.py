"""Causal SPY adaptation of licensed Dual Thrust; aggregate exports only."""
from pathlib import Path
from datetime import date
import ast
import hashlib
import json
import math
from research.studies.checkpoint_20261031.qc.capm_study import build_source as account_source
from research.studies.checkpoint_20261031.capm_review import _audit_ratios

STUDY='dual-thrust-spy-v1'
CASES=['spy','intraday','dual']
SOURCE=Path(__file__).parent/'quantconnect/sources/dual_thrust_fx_original.py'
SOURCE_SHA='58971b1adc9416803338f973a9064b8cfc813f7b8929c2eb9a27a927c2657555'


def thresholds(previous,opening):
    if len(previous)!=5 or not math.isfinite(opening) or opening<=0:raise ValueError('Five completed sessions required')
    if any(not all(math.isfinite(float(b[k])) and float(b[k])>0 for k in ['high','low','close']) or b['high']<max(b['low'],b['close']) or b['low']>b['close'] for b in previous):raise ValueError('Invalid completed OHLC')
    span=max(max(b['high'] for b in previous)-min(b['close'] for b in previous),max(b['close'] for b in previous)-min(b['low'] for b in previous))
    return opening+.5*span,opening-.5*span


EXTRA='''
def _exit(self):
    if self.time.year<2016 or CASE=='spy':
        return
    if self.portfolio[self._spy].invested:
        self.liquidate(self._spy)
    self._pending_direction=0
    self._last_target=0
    self._closed_today=True

def on_data(self,data):
    if not data.bars.contains_key(self._spy):
        return
    bar=data.bars[self._spy]
    day=self.time.date()
    if not all(math.isfinite(float(x)) and float(x)>0 for x in [bar.open,bar.high,bar.low,bar.close]) or bar.high<max(bar.open,bar.close,bar.low) or bar.low>min(bar.open,bar.close):
        raise ValueError('Invalid SPY minute OHLC')
    if self._prior_time is not None:
        elapsed=(self.time-self._prior_time).total_seconds()
        charge=self._prior_short_notional*.03*elapsed/(365*86400)
        if charge:
            self.portfolio.cash_book['USD'].add_amount(-charge)
            self._borrow+=charge
    if self._today_day!=day:
        if CASE!='spy' and self.portfolio[self._spy].invested:
            raise ValueError('Unplanned overnight position')
        self._today_day=day
        self._today=dict(high=float(bar.high),low=float(bar.low),close=float(bar.close),day=day.isoformat())
        self._close_time=self.securities[self._spy].exchange.hours.get_next_market_close(self.time.replace(hour=0,minute=0,second=0),False)
        self._cutoff=self._close_time-timedelta(minutes=5)
        self._closed_today=False
        self._pending_direction=0
        if CASE!='spy':self._last_target=0
        if len(self._sessions)==5:
            if any(date.fromisoformat(s['day'])>=day for s in self._sessions):raise ValueError('Current/future session in range')
            self._upper,self._lower=thresholds(list(self._sessions),float(bar.open))
            if self.time.year>=2016:
                self._ready_days+=1
                self._range_hash.update((day.isoformat()+'|'+format(self._upper,'.12g')+'|'+format(self._lower,'.12g')+';').encode())
        elif self.time.year>=2016:raise ValueError('Insufficient prior range seed')
    else:
        self._today['high']=max(self._today['high'],float(bar.high))
        self._today['low']=min(self._today['low'],float(bar.low))
        self._today['close']=float(bar.close)
    if self.time.year>=2016:
        if CASE=='spy':
            if not self._bought:
                if self._spy_entry_signal:
                    self.set_holdings(self._spy,.98)
                    self._bought=True
                else:self._spy_entry_signal=True
        elif self.time<self._cutoff and not self._closed_today:
            if self._pending_direction!=self._last_target:
                self.set_holdings(self._spy,.98*self._pending_direction)
                self._last_target=self._pending_direction
            # Only the next minute may execute this completed-bar decision.
            if CASE=='intraday':self._pending_direction=1
            elif float(bar.close)>self._upper:self._pending_direction=1
            elif float(bar.close)<self._lower:self._pending_direction=-1
        nav=float(self.portfolio.total_portfolio_value)
        gross=abs(float(self.portfolio[self._spy].holdings_value))/nav
        self._minute_n+=1
        self._minute_gross_sum+=gross
        self._minute_gross_max=max(self._minute_gross_max,gross)
        self._minute_peak=max(self._minute_peak,nav)
        self._minute_dd=min(self._minute_dd,nav/self._minute_peak-1)
        qty=float(self.portfolio[self._spy].quantity)
        self._long_minutes+=int(qty>0)
        self._short_minutes+=int(qty<0)
        if self.time>=self._close_time and self._last_mark!=day:
            if CASE!='spy' and self.portfolio[self._spy].invested:raise ValueError('Not flat at close')
            self._mark()
    if self.time>=self._close_time and self._last_completed!=day:
        self._sessions.append(dict(self._today))
        self._last_completed=day
    self._prior_short_notional=max(-float(self.portfolio[self._spy].holdings_value),0)
    self._prior_time=self.time
'''


def build_source(case):
    if case not in CASES or hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SOURCE_SHA:raise ValueError('Case/source identity')
    text=account_source('spy').replace("STUDY = 'capm-spy-v1'",f"STUDY = {STUDY!r}").replace("CASE = 'spy'",f"CASE = {case!r}\nSOURCE_TOKEN = 'TOKEN_PLACEHOLDER'")
    text=text.replace('ConstantSlippageModel(0.0025)','ConstantSlippageModel(0.0005)').replace("f'CAP|{CASE}|","f'DTH|{CASE}|")
    if case != 'spy':
        text=text.replace('self._fills += 1', "self._fee_models.add(type(self.securities[event.symbol].fee_model).__name__)\n            self._fills += 1")
    text=text.replace('audit=dict(first=',"audit=dict(source_token=SOURCE_TOKEN, range_hash=self._range_hash.hexdigest(), ready_days=self._ready_days, borrow_usd=round(self._borrow,6), minute_observations=self._minute_n, minute_mean_gross=round(self._minute_gross_sum/self._minute_n,10), minute_max_gross=round(self._minute_gross_max,10), minute_dd=round(self._minute_dd,12), long_minutes=self._long_minutes, short_minutes=self._short_minutes, first=")
    text=text.replace(' + self._interest\n', ' + self._interest + self._borrow\n')
    tree=ast.parse(text);tree.body=[n for n in tree.body if not (isinstance(n,ast.ClassDef) and n.name=='CapmAlphaRankingUniverseSelectionModel')]
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef));cls.name='DualThrustStudyAlgorithm'
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
    init.body=[n for n in init.body if not isinstance(n,ast.If)]
    for n in ast.walk(init):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='set_start_date':n.args=[ast.Constant(2015),ast.Constant(12),ast.Constant(21)]
    init.body+=ast.parse('''
self._sessions=deque(maxlen=5)
self._today=None
self._today_day=None
self._last_completed=None
self._upper=self._lower=None
self._pending_direction=0
self._last_target=0
self._closed_today=False
self._spy_entry_signal=False
self._prior_time=None
self._prior_short_notional=0.0
self._borrow=0.0
self._ready_days=0
self._range_hash=hashlib.sha256()
self._minute_n=0
self._minute_gross_sum=0.0
self._minute_gross_max=0.0
self._minute_peak=300000.0
self._minute_dd=0.0
self._long_minutes=0
self._short_minutes=0
self.schedule.on(self.date_rules.every_day(self._spy),self.time_rules.before_market_close(self._spy,5),self._exit)
self.debug(f'DTH_START|{CASE}|{SOURCE_TOKEN}')
''').body
    cls.body=[n for n in cls.body if not (isinstance(n,ast.FunctionDef) and n.name in ['on_data','_probe'])]+ast.parse(EXTRA).body
    end=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='on_end_of_algorithm')
    end.body=ast.parse("if len(self._rows)!=2514:\n    self.debug('DTH_INCOMPLETE|'+CASE+'|'+str(len(self._rows)))\n    return").body+end.body[2:]
    tree.body.insert(0,ast.parse('from collections import deque').body[0])
    tree.body+=ast.parse(__import__('inspect').getsource(thresholds)).body
    ast.fix_missing_locations(tree)
    notice='# Causal SPY adaptation inspired by je-suis-tm/quant-trading, Apache-2.0.\n# Original and LICENSE-JeSuisTM.txt preserved. Original FX plot example not imported.\n# Repair: previous FIVE completed sessions only; original rolling range includes current day.\n# Own native execution/accounting, next-minute signals,5bp slippage,3% short borrow.\n'
    rendered=notice+ast.unparse(tree)+'\n';token=hashlib.sha256(rendered.encode()).hexdigest()[:16];rendered=rendered.replace('TOKEN_PLACEHOLDER',token)
    if len(rendered)>=32000:raise ValueError('Cloud source limit')
    return rendered


def decode_fragments(lines,case):
    groups={}
    for line in lines:
        if 'DTH|' not in line:continue
        _,actual,seq,i,n,digest,chunk=line[line.index('DTH|'):].split('|',6)
        if actual!=case:continue
        parts=groups.setdefault((int(seq),int(n),digest),{})
        if int(i) in parts and parts[int(i)]!=chunk:raise ValueError('Conflicting packet')
        parts[int(i)]=chunk
    if not groups:raise ValueError('Missing expected packets')
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
    full=next(r for r in rows if r['kind']=='full');annual=[r for r in rows if r['kind']=='annual'];m,a=full['metrics'],full['audit']
    if len(rows)!=11 or sorted(r['year'] for r in annual)!=list(range(2016,2026)) or a['first']!='2016-01-04' or a['last']!='2025-12-31' or m['n']!=2514 or a['ready_days']!=2514:raise ValueError('Calendar/range gate')
    token=next(n.value.value for n in ast.parse(build_source(case)).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='SOURCE_TOKEN')
    if token!=a['source_token']:raise ValueError('Actual source token')
    if a['rejects'] or a['pending'] or abs(a['native_book_residual'])>2 or abs(a['native_fee_residual'])>.01 or abs(a['last_mark_residual'])>.01 or a['fee_models']!=['InteractiveBrokersFeeModel']:raise ValueError('Native accounting/execution gate')
    if a['borrow_usd']<0 or not all(math.isfinite(a[k]) for k in ['borrow_usd','minute_mean_gross','minute_max_gross','minute_dd']):raise ValueError('Intraday/borrow values')
    if case!='dual' and (a['short_minutes'] or a['borrow_usd']):raise ValueError('Unexpected short exposure')
    if not 0<=a['long_minutes']+a['short_minutes']<=a['minute_observations']:raise ValueError('Exposure count')
    if abs(m['end']/300000-1-m['ret'])>1e-9 or abs((m['end']/300000)**(365.25/(date(2025,12,31)-date(2015,12,31)).days)-1-m['cagr'])>1e-9:raise ValueError('Capital/CAGR identity')
    factor=1
    for r in annual:factor*=1+r['metrics']['ret'];_audit_ratios(r['metrics'],True)
    _audit_ratios(m,False)
    if abs(factor-1-m['ret'])>1e-8 or sum(r['metrics']['n'] for r in annual)!=m['n']:raise ValueError('Annual compounding/count')
    return dict(passed=True,case=case,calendar_hash=a['calendar_hash'],range_hash=a['range_hash'])
