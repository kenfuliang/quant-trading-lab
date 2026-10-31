"""Licensed G-Score adaptation and aggregate-only verification; no data import."""
from pathlib import Path
import ast
import hashlib
import json
import math
from research.quantconnect.capm_study import build_source as account_source
from research.capm_review import _audit_ratios

STUDY='gscore-spy-v1'
CASES=['probe','gscore','eligible','spy']
ORIGINAL=Path(__file__).parent/'quantconnect/sources/g_score_legacy_original.py'
ORIGINAL_SHA='a3958ecc57127d1b50ee9e97257d7c79381195bde3e64912f601fdc53be32d1c'


def source_selector():
    """Keep upstream seven-factor math/ranking; remove only live persistence branch."""
    if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()!=ORIGINAL_SHA:
        raise ValueError('Pinned original changed')
    tree=ast.parse(ORIGINAL.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='FineFilter')
    method.name='_source_select'
    method.body=[n for n in method.body if not (isinstance(n,ast.If) and isinstance(n.test,ast.Attribute) and n.test.attr=='LiveMode')]
    for i,n in enumerate(method.body):
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='tech_symbols':
            method.body[i+1:i+1]=ast.parse('self._eligible = list(tech_symbols)').body
            break
    method.body.insert(1, ast.parse('self._tech_count = len(tech_securities)').body[0])
    # Audit state is on the bound Python instance, never a native callback proxy.
    for i,n in enumerate(method.body):
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='tech_VARROA':
            method.body[i+1:i+1]=ast.parse('self._variance_ready = len(tech_VARROA)').body
            break
    ast.fix_missing_locations(method)
    return method


EXTRA='''
def _select(self, fundamentals):
    key=(self.time.year,self.time.month)
    if key==self._month:
        return Universe.UNCHANGED
    self._month=key
    if self.time.month%3!=1:
        return Universe.UNCHANGED
    self.quarters += 1
    fine=[f for f in fundamentals if f.has_fundamental_data]
    if not fine:
        raise ValueError('No free fundamental universe')
    if any(f.end_time.date()>self.time.date() for f in fine):
        raise ValueError('Future fundamental date')
    self._eligible=[]
    selected=self._source_select(fine)
    if self.time.month==4 and self.time.year>=2016:
        if selected is Universe.UNCHANGED or not selected or not self._eligible:
            raise ValueError('Source selection not ready after causal warmup')
        chosen=list(selected)
        row=[self.time.year,self._tech_count,len(self._eligible),len(chosen),self._variance_ready]
        self._annual_counts.append(row)
        stamp=self.time.date().isoformat()+'|'
        self._score_hash.update((stamp+','.join(sorted(str(s.id) for s in chosen))+';').encode())
        self._eligible_hash.update((stamp+','.join(sorted(str(s.id) for s in self._eligible))+';').encode())
        if CASE=='probe':
            missing=[]
            for symbol in self._eligible:
                history=self.history([symbol],1,Resolution.MINUTE)
                if history.empty or not all(float(x)>0 and math.isfinite(float(x)) for x in history.close):
                    missing.append(str(symbol.id))
            self._coverage.append([self.time.year,len(self._eligible),len(missing)])
            if missing:
                raise ValueError('Missing eligible price history count:'+str(len(missing)))
        if CASE in ['gscore','eligible']:
            targets=chosen if CASE=='gscore' else list(self._eligible)
            self._targets={s:0.98/len(targets) for s in targets}
            self._pending=True
            self._phase='sell'
    if CASE in ['probe','spy'] or self.time.year<2016:
        return []
    held=[s.symbol for s in self.securities.values() if s.invested and s.symbol!=self._spy]
    return sorted(set(list(self._targets)+held),key=lambda s:str(s.id))

def _sell(self):
    if CASE in ['probe','spy'] or not self._pending or self._phase!='sell':
        return
    if self.transactions.get_open_orders():
        raise ValueError('Pending sell-stage order')
    for holding in list(self.portfolio.values()):
        if not holding.invested:
            continue
        symbol=holding.symbol
        quantity=int(self.calculate_order_quantity(symbol,self._targets.get(symbol,0)))
        if quantity<0:
            self.market_order(symbol,quantity)
    self._phase='buy'

def _buy(self):
    if CASE=='spy' and self.time.year>=2016 and not self._bought:
        self.set_holdings(self._spy,0.98)
        self._bought=True
        return
    if CASE in ['probe','spy'] or not self._pending or self._phase!='buy':
        return
    if self.transactions.get_open_orders():
        raise ValueError('Sell stage not settled')
    for symbol in sorted(self._targets,key=lambda s:str(s.id)):
        security=self.securities[symbol]
        if not security.has_data or not security.is_tradable or security.price<=0:
            raise ValueError('Selected target not ready:'+str(symbol.id))
        quantity=int(self.calculate_order_quantity(symbol,self._targets[symbol]))
        if quantity>0:
            self.market_order(symbol,quantity)
    self._rebalances+=1
    self._pending=False
    self._phase=None
'''


def build_source(case):
    if case not in CASES:raise ValueError('Unknown study case')
    text=account_source('spy').replace("STUDY = 'capm-spy-v1'",f"STUDY = {STUDY!r}").replace("CASE = 'spy'",f"CASE = {case!r}\nSOURCE_TOKEN = 'TOKEN_PLACEHOLDER'")
    text=text.replace('ConstantSlippageModel(0.0025)','ConstantSlippageModel(0.0005)')
    text=text.replace("f'CAP|{CASE}|","f'GSC|{CASE}|")
    text=text.replace('audit=dict(first=',"audit=dict(source_token=SOURCE_TOKEN, score_hash=self._score_hash.hexdigest(), eligible_hash=self._eligible_hash.hexdigest(), annual_counts=self._annual_counts, quarters=self.quarters, rebalances=self._rebalances, mean_gross=round(self._gross_sum/len(self._rows),10), cash_only_days=self._cash_only_days, first=")
    tree=ast.parse(text)
    tree.body=[n for n in tree.body if not (isinstance(n,ast.ClassDef) and n.name=='CapmAlphaRankingUniverseSelectionModel')]
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    cls.name='GscoreStudyAlgorithm'
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
    init.body=[n for n in init.body if not (isinstance(n,ast.If) and isinstance(n.test,ast.Compare))]
    for n in ast.walk(init):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='set_start_date':n.args[0]=ast.Constant(2013)
        if isinstance(n,ast.IfExp):
            pass
    init.body+=ast.parse('''
self.tech_ROA={}
self.quarters=0
self._month=None
self._targets={}
self._pending=False
self._phase=None
self._rebalances=0
self._eligible=[]
self._annual_counts=[]
self._coverage=[]
self._score_hash=hashlib.sha256()
self._eligible_hash=hashlib.sha256()
self._gross_sum=0.0
self._cash_only_days=0
self.add_universe(self._select)
self.schedule.on(self.date_rules.every_day(self._spy),self.time_rules.after_market_open(self._spy,5),self._sell)
self.schedule.on(self.date_rules.every_day(self._spy),self.time_rules.after_market_open(self._spy,15),self._buy)
self.debug(f'GSC_START|{CASE}|{SOURCE_TOKEN}')
''').body
    cls.body=[n for n in cls.body if not (isinstance(n,ast.FunctionDef) and n.name in ['on_data','_probe'])]
    cls.body+=ast.parse('''
def on_data(self,data):
    if CASE=='probe' or self.time.year<2016 or not data.bars.contains_key(self._spy):
        return
    close=self.securities[self._spy].exchange.hours.get_next_market_close(self.time.replace(hour=0,minute=0,second=0),False)
    if self.time>=close and self._last_mark!=self.time.date():
        self._mark()
''').body
    mark=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_mark')
    for i,n in enumerate(mark.body):
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Attribute) and n.targets[0].attr=='_gross_max':
            mark.body[i+1:i+1]=ast.parse('self._gross_sum += gross\nself._cash_only_days += int(gross < 1e-10)').body
            break
    cls.body+=ast.parse(EXTRA).body+[source_selector()]
    end=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='on_end_of_algorithm')
    end.body=end.body[2:]
    end.body=ast.parse('''
if CASE=='probe':
    self._emit(dict(study=STUDY,case=CASE,kind='probe',source_token=SOURCE_TOKEN,quarters=self.quarters,annual_counts=self._annual_counts,coverage=self._coverage,score_hash=self._score_hash.hexdigest(),eligible_hash=self._eligible_hash.hexdigest(),fills=self._fills,rejects=self._rejects))
    return
if len(self._rows)!=2514:
    self.debug('GSC_INCOMPLETE|'+CASE+'|'+str(len(self._rows)))
    return
''').body+end.body
    ast.fix_missing_locations(tree)
    prefix=ORIGINAL.read_text().split('import statistics')[0]
    rendered=prefix+'# Adapted: causal2013-15 warmup;2016-25 evaluation; no ObjectStore/pickle; explicit staged execution and aggregate accounting.\nimport statistics as stat\nfrom collections import deque\n'+ast.unparse(tree)+'\n'
    token=hashlib.sha256(rendered.encode()).hexdigest()[:16]
    rendered=rendered.replace('TOKEN_PLACEHOLDER',token)
    if len(rendered)>=32000:raise ValueError('Cloud editor size limit')
    return rendered


def decode_fragments(lines,case):
    groups={}
    for line in lines:
        if 'GSC|' not in line:continue
        _,c,seq,i,n,digest,chunk=line[line.index('GSC|'):].split('|',6)
        if c!=case:continue
        parts=groups.setdefault((int(seq),int(n),digest),{})
        if int(i) in parts and parts[int(i)]!=chunk:raise ValueError('Conflicting packet')
        parts[int(i)]=chunk
    if not groups:raise ValueError('No expected packets')
    rows=[]
    for (_,n,digest),parts in sorted(groups.items()):
        if set(parts)!=set(range(n)):raise ValueError('Incomplete packets')
        raw=''.join(parts[i] for i in range(n))
        if hashlib.sha256(raw.encode()).hexdigest()[:12]!=digest:raise ValueError('Packet checksum')
        row=json.loads(raw)
        if row['study']!=STUDY or row['case']!=case:raise ValueError('Packet identity')
        rows.append(row)
    return rows


def audit_records(rows,case):
    full=rows[0] if case=='probe' else next(r for r in rows if r['kind']=='full')
    a=full if case=='probe' else full['audit']
    token=next(n.value.value for n in ast.parse(build_source(case)).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='SOURCE_TOKEN')
    if a['source_token']!=token or a['quarters']!=52 or [r[0] for r in a['annual_counts']]!=list(range(2016,2026)) or any(min(r[1:])<=0 for r in a['annual_counts']):raise ValueError('Source/quarter/annual selection gate')
    if case=='probe':
        if full['fills'] or full['rejects'] or len(full['coverage'])!=10 or any(r[2] for r in full['coverage']):raise ValueError('Free price/order-free probe gate')
        return dict(passed=True,case=case,score_hash=a['score_hash'],eligible_hash=a['eligible_hash'])
    annual=[r for r in rows if r['kind']=='annual']
    m=full['metrics']
    if len(rows)!=11 or sorted(r['year'] for r in annual)!=list(range(2016,2026)) or m['n']!=2514 or a['first']!='2016-01-04' or a['last']!='2025-12-31':raise ValueError('Calendar gate')
    if a['rejects'] or a['pending'] or abs(a['native_book_residual'])>2 or abs(a['native_fee_residual'])>.01 or abs(a['last_mark_residual'])>.01:raise ValueError('Native accounting/execution gate')
    if a['fee_models']!=['InteractiveBrokersFeeModel'] or a['rebalances']!=(10 if case!='spy' else 0):raise ValueError('Actual fee model/rebalances')
    if abs(m['end']/300000-1-m['ret'])>1e-9:raise ValueError('Capital identity')
    _audit_ratios(m,False);factor=1
    for r in annual:factor*=1+r['metrics']['ret'];_audit_ratios(r['metrics'],True)
    if abs(factor-(1+m['ret']))>1e-8 or sum(r['metrics']['n'] for r in annual)!=m['n']:raise ValueError('Annual compounding/count')
    return dict(passed=True,case=case,score_hash=a['score_hash'],eligible_hash=a['eligible_hash'],calendar_hash=a['calendar_hash'])
