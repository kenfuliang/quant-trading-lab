import ast,unittest
from pathlib import Path
from scripts.prepare_selection_completion_probe import adapt
ROOT=Path(__file__).resolve().parents[1]
class ReadinessProbeTests(unittest.TestCase):
 @unittest.skipUnless((ROOT/'.local/qc-breadth-v1/asset-source.py').exists(),'Private saved adapter excluded')
 def test_observer_preserves_financial_selection_but_never_executes(self):
  source=ast.parse((ROOT/'.local/qc-breadth-v1/asset-source.py').read_text());new=ast.parse(adapt('asset_probe','asset'))
  original=next(n for n in ast.walk(source) if isinstance(n,ast.FunctionDef) and n.name=='_refresh_weights')
  fn=next(n for n in ast.walk(new) if isinstance(n,ast.FunctionDef) and n.name=='_refresh_weights')
  self.assertEqual([ast.dump(n) for n in original.body],[ast.dump(n) for n in fn.body[:-1]])
  on=next(n for n in ast.walk(new) if isinstance(n,ast.FunctionDef) and n.name=='on_data')
  calls=[n.func.attr for n in ast.walk(on) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
  self.assertEqual(calls,['_refresh_weights'])
  compile(ast.unparse(new),'probe','exec')
 def test_diagnostic_only_exports_metadata(self):
  s=(ROOT/'research/quantconnect/selection_readiness_probe.py').read_text()
  self.assertNotIn('market_on_open_order',s);self.assertNotIn("close=float",s)
  self.assertIn('self.transactions.get_orders()',s)
 @unittest.skipUnless((ROOT/'.local/qc-breadth-v1/asset-source.py').exists(),'Private saved adapters excluded')
 def test_both_stock_cohorts_are_order_free_and_use_their_own_universe(self):
  from scripts.prepare_selection_completion_probe import cohort_adapt
  for mode in ('momentum','lowvol'):
   tree=ast.parse(cohort_adapt('stock_probe',mode));assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and n.targets[0].id=='MODE');self.assertEqual(assignment.value.value,mode)
   on=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='on_data')
   calls=[n.func.attr for n in ast.walk(on) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)];self.assertEqual(calls,['_refresh_weights'])
   end=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_diag_end');self.assertIn('self.transactions.get_orders()',ast.unparse(end))
