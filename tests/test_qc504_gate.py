import ast,unittest,math,statistics
from collections import deque
from pathlib import Path
import pandas as pd
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from research.risk_gate import states
from scripts.prepare_qc504_gate import adapt
ROOT=Path(__file__).resolve().parents[1]
class GateTransferTests(unittest.TestCase):
 def core(self):
  tree=ast.parse((ROOT/'research/quantconnect/sector_comparison.py').read_text())
  cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GateCore')
  for n in ast.walk(cls):
   if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='dd' for t in n.targets):n.value=ast.Constant(0.)
  ast.fix_missing_locations(cls)
  scope=dict(deque=deque,math=math,statistics=statistics)
  exec(compile(ast.Module(body=[cls],type_ignores=[]),'core','exec'),scope)
  return scope['GateCore']()
 def test_online_retained_variant_parity(self):
  values=[round(100*math.exp(.0002*i+.06*math.sin(i/9))*(1+.03*math.sin(i*2.3) if 300<i<360 else 1),2) for i in range(700)]
  s=pd.Series(values);frame=pd.DataFrame(dict(fast=s.ewm(span=50,adjust=False,min_periods=50).mean(),slow=s.ewm(span=200,adjust=False,min_periods=200).mean(),vol=s.pct_change().rolling(20).std()*math.sqrt(252),dd=0.))
  expected=states(frame);g=self.core()
  for i,x in enumerate(values):
   g.update(x);self.assertEqual(g.state,expected.iloc[i].state);self.assertEqual(g.cap,expected.iloc[i].cap)
 def test_cap_changes_weight_intent(self):
  from research.quantconnect.t11_gate_policy import gated_t11_weights
  class Fake:
   def _ungated_t11_weights(self):return dict(TQQQ=.5,SQQQ=.5)
  f=Fake();f._gate=self.core()
  intents=[]
  for state in ('green','yellow','red'):
   f._gate.state=state;weights=gated_t11_weights(f);intents.append(tuple(sorted(weights.items())))
   self.assertAlmostEqual(.9*sum(weights.values()),dict(green=.9,yellow=.45,red=0)[state])
  self.assertEqual(len(set(intents)),3)
 def test_observer_rejects_future_missing_duplicate(self):
  import research.quantconnect.t11_gate_policy as policy
  class History:
   def __init__(self,bars):self.bars=bars
   def __getitem__(self,key):return lambda *a,**kw:self.bars
  close=datetime(2020,1,2,16);bar=SimpleNamespace(time=datetime(2020,1,2),end_time=close,close=100)
  data=SimpleNamespace(bars={'SPY':bar})
  for bars,last in (([],None),([SimpleNamespace(time=bar.time,end_time=datetime(2020,1,3),close=100)],None),([bar],close.date())):
   f=SimpleNamespace(_syms={'SPY':'SPY'},history=History(bars),time=close,_gate_last=last)
   with patch.multiple(policy,TradeBar=object,Resolution=SimpleNamespace(DAILY=1),DataNormalizationMode=SimpleNamespace(RAW=1),create=True):
    with self.assertRaises(ValueError):policy.gate_observe(f,data)
 @unittest.skipUnless((ROOT/'.local/qc504-funded-v1/t11-source.py').exists(),'Private upstream source is intentionally excluded from repository')
 def test_generated_control_financial_functions_unchanged(self):
  for case in ('ensemble','t11'):
   source=(ROOT/f'.local/qc504-funded-v1/{case}-source.py').read_text();adapt(source,case)
