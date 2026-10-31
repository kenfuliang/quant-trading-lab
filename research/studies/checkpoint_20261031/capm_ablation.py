"""Bounded CAPM cost/stop factorial; aggregate outputs only, no market paths."""
from pathlib import Path
from datetime import date
import ast
import hashlib
import json
import math
from research.studies.checkpoint_20261031.qc.capm_study import build_source as prior_source
from research.studies.checkpoint_20261031.capm_review import _audit_ratios

STUDY = 'capm-ablation-v1'
COSTS = {'zero': dict(slippage=0.0, fee_model='ConstantFeeModel'),
         'fees': dict(slippage=0.0, fee_model='InteractiveBrokersFeeModel'),
         'stress': dict(slippage=0.0025, fee_model='InteractiveBrokersFeeModel')}
CASES = {
    'c25_on': ('capm','stress',True), 'c0_on': ('capm','zero',True),
    'c0_off': ('capm','zero',False), 'cf_on': ('capm','fees',True),
    'cf_off': ('capm','fees',False), 'c25_off': ('capm','stress',False),
    's0': ('spy','zero',False), 'sf': ('spy','fees',False), 's25': ('spy','stress',False)}


def build_source(case):
    if case not in CASES:
        raise ValueError('Unknown ablation case')
    mode,cost,stop = CASES[case]
    text = prior_source(mode)
    text = text.replace("STUDY = 'capm-spy-v1'", f"STUDY = {STUDY!r}")
    text = text.replace(f"CASE = {mode!r}", f"CASE = {mode!r}\nCASE_ID = {case!r}\nCOST_MODE = {cost!r}\nSTOP_ENABLED = {stop!r}\nSOURCE_TOKEN = 'TOKEN_PLACEHOLDER'")
    text = text.replace('case=CASE,', 'case=CASE_ID,')
    text = text.replace("f'CAP|{CASE}|", "f'ABL|{CASE_ID}|")
    text = text.replace('import hashlib', "import hashlib\nSELECTION_AUDIT = {'count': 0, 'digest': hashlib.sha256()}")
    text = text.replace('ConstantSlippageModel(0.0025)', f"ConstantSlippageModel({COSTS[cost]['slippage']!r})")
    if cost == 'zero':
        text = text.replace('security.set_margin_interest_rate_model(', 'security.set_fee_model(ConstantFeeModel(0))\n        security.set_margin_interest_rate_model(')
        text = text.replace("name != 'InteractiveBrokersFeeModel'", "name != 'ConstantFeeModel'")
    if mode == 'capm' and not stop:
        text = text.replace('self.set_risk_management(MaximumDrawdownPercentPerSecurity(0.01))', 'self.set_risk_management(NullRiskManagementModel())')
    text = text.replace('self._rows = []', "self._rows = []\n        self._selection_digest = hashlib.sha256()\n        self._selection_count = 0\n        self._gross_sum = 0.0\n        self._cash_only_days = 0")
    text = text.replace('self._log_bytes = 0', "self._log_bytes = 0\n        self._dependency_smoke = (type(NullRiskManagementModel()).__name__, type(ConstantFeeModel(0)).__name__)\n        self.debug(f'ABL_START|{CASE_ID}|{COST_MODE}|{STOP_ENABLED}|{SOURCE_TOKEN}')")
    text = text.replace('self._gross_max = max(self._gross_max, gross)', 'self._gross_max = max(self._gross_max, gross)\n        self._gross_sum += gross\n        self._cash_only_days += int(gross < 1e-10)')
    text = text.replace('audit=dict(first=', "audit=dict(case_id=CASE_ID, cost_mode=COST_MODE, stop_enabled=STOP_ENABLED, source_token=SOURCE_TOKEN, selection_hash=SELECTION_AUDIT['digest'].hexdigest(), selection_count=SELECTION_AUDIT['count'], mean_gross=round(self._gross_sum/len(self._rows), 10), cash_only_days=self._cash_only_days, first=")
    tree = ast.parse(text)
    universe = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CapmAlphaRankingUniverseSelectionModel')
    selector = next(n for n in universe.body if isinstance(n,ast.FunctionDef) and n.name=='select_pair')
    original_return = selector.body.pop()
    if not isinstance(original_return,ast.Return):
        raise ValueError('Source selector changed')
    selector.body += ast.parse('''selected = PLACEHOLDER
SELECTION_AUDIT['count'] += 1
SELECTION_AUDIT['digest'].update((algorithm.utc_time.isoformat()+'|'+','.join(str(x.id) for x in selected)+';').encode())
return selected''').body
    selector.body[-4].value = original_return.value
    ast.fix_missing_locations(tree)
    # Preserve the original Apache header, which ast.unparse does not retain.
    notice = text[:text.index('STUDY =')]
    rendered = notice + ast.unparse(tree) + '\n'
    token = hashlib.sha256(rendered.encode()).hexdigest()[:16]
    rendered = rendered.replace('TOKEN_PLACEHOLDER',token)
    if len(rendered) >= 32000:
        raise ValueError('Cloud editor size limit')
    return rendered


def decode_fragments(texts, case):
    groups = {}
    for line in texts:
        if 'ABL|' not in line:
            continue
        _, actual, seq, idx, total, digest, chunk = line[line.index('ABL|'):].split('|',6)
        if actual != case:
            continue
        parts = groups.setdefault((int(seq),int(total),digest),{})
        idx = int(idx)
        if idx in parts and parts[idx] != chunk:
            raise ValueError('Conflicting fragment')
        parts[idx] = chunk
    if not groups:
        raise ValueError('No fragments for expected case')
    output = []
    for (_,total,digest),parts in sorted(groups.items()):
        if set(parts)!=set(range(total)):
            raise ValueError('Missing fragment')
        raw = ''.join(parts[i] for i in range(total))
        if hashlib.sha256(raw.encode()).hexdigest()[:12] != digest:
            raise ValueError('Fragment checksum failed')
        payload=json.loads(raw)
        if payload.get('study')!=STUDY or payload.get('case')!=case:
            raise ValueError('Study/case mismatch')
        output.append(payload)
    return output


def audit_records(records, case):
    mode,cost,stop = CASES[case]
    annual = [r for r in records if r['kind']=='annual']
    fulls = [r for r in records if r['kind']=='full']
    if len(fulls)!=1 or sorted(r['year'] for r in annual)!=list(range(2016,2026)):
        raise ValueError('Missing/duplicated periods')
    full=fulls[0];m=full['metrics'];a=full['audit']
    if any(r['case']!=case or r['study']!=STUDY for r in records):
        raise ValueError('Record identity failed')
    if a['case_id']!=case or a['cost_mode']!=cost or a['stop_enabled']!=stop:
        raise ValueError('Actual cost/stop configuration failed')
    source=build_source(case)
    token=next(n.value.value for n in ast.parse(source).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='SOURCE_TOKEN')
    if a['source_token']!=token:
        raise ValueError('Actual source token failed')
    if a['fee_models']!=[COSTS[cost]['fee_model']] or (cost=='zero' and abs(a['fees'])>1e-8):
        raise ValueError('Actual fee model failed')
    if a['first']!='2016-01-04' or a['last']!='2025-12-31' or m['n']!=2514:
        raise ValueError('Closing calendar failed')
    if a['rejects'] or a['pending'] or abs(a['native_book_residual'])>2 or abs(a['native_fee_residual'])>.01 or abs(a['last_mark_residual'])>.01:
        raise ValueError('Native execution/accounting failed')
    if not all(math.isfinite(float(a[k])) for k in ['fees','interest','max_gross','mean_gross','min_cash','native_book_residual']) or min(a['fees'],a['interest'])<0:
        raise ValueError('Invalid accounting values')
    if abs(m['end']/300000-1-m['ret'])>1e-9:
        raise ValueError('Ending capital failed')
    days=(date.fromisoformat(a['last'])-date(2015,12,31)).days
    if abs((m['end']/300000)**(365.25/days)-1-m['cagr'])>1e-9:
        raise ValueError('CAGR failed')
    factor=1.0
    for row in annual:
        factor*=1+row['metrics']['ret'];_audit_ratios(row['metrics'],True)
    _audit_ratios(m,False)
    if abs(factor-(1+m['ret']))>1e-8 or sum(r['metrics']['n'] for r in annual)!=m['n']:
        raise ValueError('Annual compounding/count failed')
    expected_selections=120 if mode=='capm' else 0
    if a['selection_count']!=expected_selections:
        raise ValueError('Selection cadence failed')
    return dict(passed=True,case=case,calendar_hash=a['calendar_hash'],selection_hash=a['selection_hash'],source_token=token,fee_model=COSTS[cost]['fee_model'])


def factorial_effects(results):
    full=lambda c: next(r for r in results[c] if r['kind']=='full')
    output=[]
    periods=[('full',None)]+[('annual',y) for y in range(2016,2026)]
    for kind,year in periods:
        def metrics(c):
            return next(r['metrics'] for r in results[c] if r['kind']==kind and (kind=='full' or r['year']==year))
        keys=['cagr' if kind=='full' else 'ret','dd','sharpe','calmar' if kind=='full' else 'annual_calmar','uw_fraction','longest_uw','longest_uw_days']
        for key in keys:
            v={c:metrics(c)[key] for c in results}
            diff=lambda a,b: None if v[a] is None or v[b] is None else v[a]-v[b]
            base={'kind':kind,'year':year,'metric':key}
            for on,off,cost in [('c0_on','c0_off','zero'),('cf_on','cf_off','fees'),('c25_on','c25_off','stress')]:
                output.append(dict(**base,effect='stop_on_minus_off',cost=cost,value=diff(on,off)))
            for stop,suffix in [(True,'on'),(False,'off')]:
                output.append(dict(**base,effect='fees_minus_zero',stop=stop,value=diff('cf_'+suffix,'c0_'+suffix)))
                output.append(dict(**base,effect='stress_minus_fees',stop=stop,value=diff('c25_'+suffix,'cf_'+suffix)))
            vals=[v[c] for c in ['c25_on','c25_off','c0_on','c0_off']]
            output.append(dict(**base,effect='total_cost_stop_interaction',value=None if any(x is None for x in vals) else (vals[0]-vals[1])-(vals[2]-vals[3])))
    return output
