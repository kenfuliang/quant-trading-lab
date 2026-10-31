"""Freeze nine predeclared cases only after verified order-free diagnosis."""
import ast,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/selection-completion-v1'
CASES={'asset':('asset',False,False),'stock':('momentum',False,False),'lowvol':('lowvol',False,False),'spy':('spy',False,False),'ew_asset':('asset',True,False),'ew_stock':('momentum',True,False),'ew_low':('lowvol',True,False),'stress':('momentum',False,True),'ew_stress':('momentum',True,True)}
def generate(case):
 mode,eq,stress=CASES[case]
 t=ast.parse((RAW.parent/f'qc-breadth-v1/{mode}-source.py').read_text());cls=next(n for n in t.body if isinstance(n,ast.ClassDef))
 for n in ast.walk(t):
  if isinstance(n,ast.Constant) and n.value=='qc-breadth-v1':n.value='selection-completion-v1'
 next(n for n in t.body if isinstance(n,ast.Assign) and n.targets[0].id=='AUDIT_CASE').value=ast.Constant(case)
 replacement=ast.parse((ROOT/'research/quantconnect/selection_completion_policy.py').read_text())
 names={n.name for n in replacement.body if isinstance(n,ast.FunctionDef)}
 cls.body=[n for n in cls.body if not(isinstance(n,ast.FunctionDef) and n.name in names)]
 cls.body += [n for n in replacement.body if isinstance(n,ast.FunctionDef)]
 t.body[:0]=ast.parse(f'from datetime import timedelta\nEQUAL_WEIGHT={eq!r}\nSTRESS={stress!r}').body
 init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
 init.body+=ast.parse('self._feature_hash=hashlib.sha256()\nself._feature_future=self._feature_invalid=self._feature_unordered=0\nself._delay_pending=False\nself._delay_session=None').body
 config=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='configure_security')
 for n in ast.walk(config):
  if isinstance(n,ast.Constant) and n.value==.0025:n.value=.005 if stress else .0025
 # Technical lifecycle repair after the preserved broad-control failure.
 if case in ('ew_stock','stress','ew_stress'):
  retained=next(n for n in ast.parse((ROOT/'research/quantconnect/selection_subscription_retention.py').read_text()).body if isinstance(n,ast.FunctionDef))
  retained.name='_retained_targets';cls.body.append(retained)
  selector=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='select_universe')
  selector.body[-1]=ast.parse('return self._retained_targets()').body[0]
 # Cash feasibility reserve must match actual slippage; all other funded AST stays unchanged.
 for fn in cls.body:
  if isinstance(fn,ast.FunctionDef) and fn.name.startswith('_fund'):
   for n in ast.walk(fn):
    if isinstance(n,ast.Constant) and n.value==.0025:n.value=.005 if stress else .0025
    if isinstance(n,ast.Constant) and n.value==1.0025:n.value=1.005 if stress else 1.0025
 emit=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_audit_emit')
 emit.body[:0]=ast.parse("""
if payload.get('kind')=='overall':
    payload=dict(payload,feature_sha256=self._feature_hash.hexdigest(),feature_future=self._feature_future,feature_invalid=self._feature_invalid,feature_unordered=self._feature_unordered)
""").body
 # Compact aggregate attribution instead of empty values, without exporting vendor inputs.
 for n in ast.walk(emit):
  if isinstance(n,ast.Constant) and n.value==145:n.value=130
 for i,n in enumerate(emit.body):
  if isinstance(n,ast.If) and "values=[]" in ast.unparse(n):
   emit.body[i]=ast.parse("""
if payload.get('kind')=='assets':
    values=payload['values'];pos=sum(max(0,x[1]) for x in values);neg=sum(min(0,x[1]) for x in values)
    payload=dict(payload,values=values[:2]+values[-2:] if len(values)>4 else values,asset_count=len(values),positive_pnl=pos,negative_pnl=neg,largest_gain_share=values[0][1]/pos if pos else None)
""").body[0]
 return ast.unparse(ast.fix_missing_locations(t))+'\n'
def main():
 ledger=RAW/'attempts.json';j=json.loads(ledger.read_text())
 if j['status']!='diagnosis-verified':raise ValueError('Verified diagnosis required')
 hashes={}
 for case in CASES:
  p=RAW/f'{case}-source.py'
  if p.exists():raise ValueError('Do not overwrite frozen source')
  p.write_text(generate(case));compile(p.read_text(),str(p),'exec');assert p.stat().st_size<32768;hashes[case]=hashlib.sha256(p.read_bytes()).hexdigest()
 plan=json.loads((ROOT/'research/plans/selection-completion-v1.design.json').read_text())
 plan.update(status='frozen-before-financial-results',source_hashes=hashes,deadline_utc=j['deadline_utc'],case_mapping=CASES,history='Explicit600calendar-day SCALED_RAW request ending at currentcompleted close; require last253positivefinite ordered unique bars and current slice timestamp. Missing slots cash.',timing='First observed SPY close of month; shared staged MOO. Stress holds old targets one extra observed SPY session before releasing new intent.',diagnosis=json.loads((RAW/'diagnosis.json').read_text()))
 (ROOT/'research/plans/selection-completion-v1.json').write_text(json.dumps(plan,indent=2)+'\n')
 j['source_hashes'].update(hashes);j['status']='financial-active';ledger.write_text(json.dumps(j,indent=2)+'\n');print(hashes)
if __name__=='__main__':main()
