"""Build a private plaintext diagnostic adapter; no network or financial execution."""
import ast
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'.local/qc504-v1'
CASES={'recent':(2020,None),'long':(2010,None),'cost25':(2020,.0025)}

def build(case):
    year,slip=CASES[case]
    original=(RAW/'published-main.py').read_text()
    tree=ast.parse(original)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    # Add reporting only; preserve all four trading-rule and rebalance ASTs.
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='initialize')
    for node in ast.walk(init):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            if node.func.attr=='set_start_date':node.args=[ast.Constant(year),ast.Constant(1),ast.Constant(1)]
            if node.func.attr=='set_end_date':node.args=[ast.Constant(2025),ast.Constant(12),ast.Constant(31)]
    init.body+=ast.parse('self._audit_initialize()').body
    if slip is not None:
        init.body+=ast.parse(f'for sym in self._syms.values():\n    self.securities[sym].set_slippage_model(ConstantSlippageModel({slip}))').body
    # Redirect legacy debug output. No signal or order expressions are changed.
    for node in ast.walk(cls):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='log':
            node.func.attr='_audit_quiet_log'
    cls.body=[n for n in cls.body if not (isinstance(n,ast.FunctionDef) and n.name in ('on_data','on_end_of_algorithm'))]
    cls.body+=ast.parse('''
def on_data(self, data):
    if self.is_warming_up:
        return
    self._rebalance()
    self._audit_record(data)
def on_order_event(self, event):
    self._audit_order(event)
def on_end_of_algorithm(self):
    self._audit_end()
def _audit_quiet_log(self, message):
    pass
''').body
    addon=ast.parse((ROOT/'research/quantconnect/qc504_audit.py').read_text())
    for fn in addon.body:
        if isinstance(fn,ast.FunctionDef):
            fn.name='_'+fn.name
            cls.body.append(fn)
    helpers=(ROOT/'research/quantconnect/sector_metrics.py').read_text()
    header=f'import hashlib\nimport json\nAUDIT_CASE={case!r}\nAUDIT_START_YEAR={year}\n'
    result=header+helpers+'\n'+ast.unparse(ast.fix_missing_locations(tree))+'\n'
    dest=RAW/f'{case}-source.py';dest.write_text(result)
    return dest

if __name__=='__main__':
    for case in CASES:
        p=build(case);print(case,hashlib.sha256(p.read_bytes()).hexdigest())
