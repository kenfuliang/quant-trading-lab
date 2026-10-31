"""Freeze order-free diagnosis from the exact previously run adapters."""
import ast,json,hashlib,subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/selection-completion-v1'
def adapt(case,base):
 t=ast.parse((ROOT/f'.local/qc-breadth-v1/{base}-source.py').read_text());cls=next(n for n in t.body if isinstance(n,ast.ClassDef))
 for n in ast.walk(t):
  if isinstance(n,ast.Constant) and n.value=='qc-breadth-v1':n.value='selection-completion-v1'
 next(n for n in t.body if isinstance(n,ast.Assign) and n.targets[0].id=='AUDIT_CASE').value=ast.Constant(case)
 init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize');init.body+=ast.parse('self._diag_initialize()').body
 refresh=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_refresh_weights');refresh.body+=ast.parse('self._diag_record(data)').body
 cls.body=[n for n in cls.body if not(isinstance(n,ast.FunctionDef) and n.name in ('on_data','on_end_of_algorithm'))]
 cls.body+=ast.parse('''
def on_data(self,data):
    if self.is_warming_up or self._syms['SPY'] not in data.bars:return
    self._refresh_weights(data)
def on_end_of_algorithm(self):self._diag_end()
''').body
 for n in ast.parse((ROOT/'research/quantconnect/selection_readiness_probe.py').read_text()).body:
  if isinstance(n,ast.FunctionDef):n.name='_'+n.name;cls.body.append(n)
 # Avoid funding/result additions and omit financial summaries in this order-free run.
 emit=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_audit_emit')
 emit.body=[n for n in emit.body if not isinstance(n,ast.If)]+[]
 for n in ast.walk(emit):
  if isinstance(n,ast.Constant) and n.value==145:n.value=120
 return ast.unparse(ast.fix_missing_locations(t))+'\n'
def cohort_adapt(case,base):
 t=ast.parse(adapt(case,base));cls=next(n for n in t.body if isinstance(n,ast.ClassDef))
 cls.body=[n for n in cls.body if not(isinstance(n,ast.FunctionDef) and n.name.startswith('_diag_'))]
 for n in ast.parse((ROOT/'research/quantconnect/selection_stock_probe.py').read_text()).body:
  if isinstance(n,ast.FunctionDef):n.name='_'+n.name;cls.body.append(n)
 init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
 init.body+=ast.parse("for ticker in ['EFA','BND','VNQ','GSG']:\n    self._syms[ticker]=self.add_equity(ticker,Resolution.DAILY).symbol\n    self.configure_security(self.securities[self._syms[ticker]])").body
 t.body.insert(0,ast.ImportFrom(module='datetime',names=[ast.alias(name='timedelta')],level=0))
 return ast.unparse(ast.fix_missing_locations(t))+'\n'
def main():
 RAW.mkdir(exist_ok=False)
 out=RAW/'asset_probe-source.py';out.write_text(adapt('asset_probe','asset'))
 now=datetime.now(timezone.utc);deadline=(now+timedelta(minutes=120)).isoformat()
 record=dict(study_id='selection-completion-v1',status='diagnosis-active',created_utc=now.isoformat(),deadline_utc=deadline,max_total_attempts=14,max_diagnostics=2,max_financial_cases=9,max_technical_retries=3,git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_hashes={'asset_probe':hashlib.sha256(out.read_bytes()).hexdigest()},attempts=[])
 (RAW/'attempts.json').write_text(json.dumps(record,indent=2)+'\n');print(deadline,record['source_hashes'])
if __name__=='__main__':main()
