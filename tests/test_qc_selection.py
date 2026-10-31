"""Offline checks of interpretation, causality and shared controller identity."""
import ast,math,statistics,unittest
from pathlib import Path
from scripts.prepare_qc_breadth import generate
ROOT=Path(__file__).resolve().parents[1]
def functions():
 tree=ast.parse((ROOT/'research/quantconnect/selection_candidates.py').read_text())
 selected=[n for n in tree.body if isinstance(n,ast.FunctionDef)];scope=dict(statistics=statistics)
 exec(compile(ast.Module(body=selected,type_ignores=[]),'formulas','exec'),scope);return scope
class SelectionTests(unittest.TestCase):
 def test_momentum_percent_not_dollars(self):
  f=functions()['percent_momentum'];self.assertGreater(f([10,15]),f([100,120]));self.assertEqual(f([10,15]),f([100,150]))
 def test_volatility_scale_invariant(self):
  f=functions()['return_volatility'];a=[100,101,99,104];self.assertAlmostEqual(f(a),f([10*x for x in a]))
 def test_constant_return_volatility(self):
  self.assertLess(functions()['return_volatility']([100*1.01**n for n in range(253)]),1e-12)
 def test_initial_buyhold_is_not_monthly_maintenance(self):
  tree=ast.parse((ROOT/'research/quantconnect/selection_candidates.py').read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_refresh_weights')
  spy=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.If) and ast.unparse(n.test)=="MODE == 'spy'")
  reset=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='self._fund_intent')
  self.assertLess(spy,reset);self.assertIsInstance(fn.body[spy].body[-1],ast.Return)
 def test_dynamic_initializer_retains_brokerage_defaults(self):
  tree=ast.parse((ROOT/'research/quantconnect/selection_candidates.py').read_text())
  calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
  self.assertIn('add_security_initializer',calls);self.assertNotIn('set_security_initializer',calls)
  fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='configure_security')
  scope={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'initializer','exec'),scope)
  from types import SimpleNamespace
  with self.assertRaises(ValueError):scope['configure_security'](object(),SimpleNamespace(fee_model=object()))
 def test_removed_unheld_monthly_target_keeps_subscription(self):
  tree=ast.parse((ROOT/'research/quantconnect/selection_candidates.py').read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='select_universe')
  scope=dict(MODE='lowvol',math=math);exec(compile(ast.Module(body=[fn],type_ignores=[]),'selection','exec'),scope)
  from collections import namedtuple
  from datetime import datetime
  from types import SimpleNamespace
  import hashlib
  Symbol=namedtuple('Symbol','id');old=Symbol('old-unheld-target');new=Symbol('new-top50')
  self_state=SimpleNamespace(time=datetime(2020,2,3),_universe_month=None,_universe_calls=0,_fundamental_valid=0,_membership_hash=hashlib.sha256(),_weights={old:.2})
  f=SimpleNamespace(has_fundamental_data=True,price=20,dollar_volume=10000,market_cap=100000,symbol=new)
  returned=scope['select_universe'](self_state,[f]);self.assertIn(old,returned);self.assertIn(new,returned);self.assertEqual(self_state._selected,[new])
 @unittest.skipUnless((ROOT/'.local/qc504-funded-v1/t11-source.py').exists(),'Private original source excluded')
 def test_funded_controller_unchanged_and_sources_compile(self):
  original=ast.parse((ROOT/'.local/qc504-funded-v1/t11-source.py').read_text())
  funcs={n.name:ast.dump(n) for n in ast.walk(original) if isinstance(n,ast.FunctionDef) and n.name.startswith('_fund')}
  for mode in ('asset','momentum','lowvol','spy','t11'):
   text=generate(mode);compile(text,mode,'exec');self.assertLess(len(text.encode()),32768)
   new={n.name:ast.dump(n) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.FunctionDef) and n.name.startswith('_fund')}
   self.assertEqual(new,funcs)
