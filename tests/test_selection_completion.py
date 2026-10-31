import ast,hashlib,math,statistics,unittest
from collections import deque,namedtuple
from datetime import datetime,timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from scripts.prepare_selection_completion import generate,CASES
ROOT=Path(__file__).resolve().parents[1]
Symbol=namedtuple('Symbol','id')
class History:
 def __init__(self,rows):self.rows=rows
 def __getitem__(self,k):return lambda *a,**kw:self.rows

def fixture(eq=False,stress=False,count=253):
 now=datetime(2020,2,3,16);syms=[Symbol('a'),Symbol('b')]
 rows=[{s:NS(end_time=now-timedelta(days=count-1-i),close=(100+i if s.id=='a' else 100)) for s in syms} for i in range(count)]
 scope=dict(MODE='momentum',EQUAL_WEIGHT=eq,STRESS=stress,deque=deque,timedelta=timedelta,TradeBar=object,Resolution=NS(DAILY=1),DataNormalizationMode=NS(SCALED_RAW=1),math=math,percent_momentum=lambda x:x[-1]/x[0]-1,return_volatility=lambda x:statistics.stdev([b/a-1 for a,b in zip(x,x[1:])]))
 tree=ast.parse((ROOT/'research/quantconnect/selection_completion_policy.py').read_text());exec(compile(tree,'policy','exec'),scope)
 state=NS(time=now,_selected=syms,_syms={'SPY':syms[0]},_decision_month=None,_selection_events=0,_history_seeded=0,_history_short=0,_ready_counts=[],_feature_hash=hashlib.sha256(),_feature_future=0,_feature_invalid=0,_feature_unordered=0,history=History(rows),_weights={},_fund_intent='old',_delay_pending=False,is_warming_up=False)
 data=NS(bars={s:NS(end_time=now,time=now) for s in syms})
 return state,data,scope,rows
class CompletionTests(unittest.TestCase):
 def test_short_history_stays_ineligible(self):
  s,d,f,r=fixture(count=252);f['_refresh_weights'](s,d);self.assertEqual(s._weights,{});self.assertEqual(s._history_short,2)
 def test_future_and_duplicate_and_invalid_fail_closed(self):
  for kind in ('future','duplicate','invalid'):
   s,d,f,r=fixture()
   if kind=='future':r[-1][s._selected[0]].end_time+=timedelta(days=1)
   if kind=='duplicate':r[-1][s._selected[0]].end_time=r[-2][s._selected[0]].end_time
   if kind=='invalid':r[-1][s._selected[0]].close=float('nan')
   with self.subTest(kind=kind),self.assertRaises(ValueError):f['_refresh_weights'](s,d)
 def test_current_slice_timestamp_required(self):
  s,d,f,r=fixture();d.bars[s._selected[0]].end_time-=timedelta(days=1);f['_refresh_weights'](s,d);self.assertEqual(len(s._weights),1)
 def test_equal_weight_same_eligible_hash_and_explicit_cash_slots(self):
  s,d,f,r=fixture();f['_refresh_weights'](s,d)
  e,ed,ef,_=fixture(eq=True);ef['_refresh_weights'](e,ed)
  self.assertEqual(s._feature_hash.hexdigest(),e._feature_hash.hexdigest());self.assertAlmostEqual(sum(s._weights.values()),.4);self.assertEqual(sum(e._weights.values()),1)
 def test_stress_releases_one_session_later(self):
  s,d,f,r=fixture(stress=True);s._refresh_weights=lambda data:f['_refresh_weights'](s,data);s._fund_accrue=lambda date:None;s._funded_rebalance=lambda:None;s._audit_record=lambda data:None;s.portfolio=NS(cash=10000)
  f['on_data'](s,d);self.assertTrue(s._delay_pending);self.assertEqual(s._weights,{})
  s.time+=timedelta(days=1)
  for b in d.bars.values():b.time+=timedelta(days=1);b.end_time+=timedelta(days=1)
  f['on_data'](s,d);self.assertFalse(s._delay_pending);self.assertEqual(len(s._weights),2);self.assertIsNone(s._fund_intent)
 @unittest.skipUnless((ROOT/'.local/qc-breadth-v1/asset-source.py').exists(),'Private adapters not distributed')
 def test_all_compile_and_controller_preserved_except_declared_stress_reserve(self):
  for c,(mode,eq,stress) in CASES.items():
   original=ast.parse((ROOT/f'.local/qc-breadth-v1/{mode}-source.py').read_text());new=ast.parse(generate(c));compile(new,c,'exec')
   def funds(t):return {n.name:ast.dump(n) for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name.startswith('_fund')}
   if stress:
    for n in ast.walk(original):
     if isinstance(n,ast.Constant) and n.value==1.0025:n.value=1.005
   self.assertEqual(funds(original),funds(new),c)

class FragmentIntegrityTests(unittest.TestCase):
 def test_long_case_roundtrip_and_truncation_rejected(self):
  import json
  from scripts.parse_selection_completion_fragments import decode
  case='stock_probe';line=json.dumps(dict(study='selection-completion-v1',case=case,kind='readiness',counts=[['2023-07-03',50,0,50]]*72),separators=(',',':'));digest=hashlib.sha256(line.encode()).hexdigest()[:12]
  chunks=[line[i:i+120] for i in range(0,len(line),120)];texts=[f'2025-12-31 16:00:00 QCA|{case}|1|{i}|{len(chunks)}|{digest}|{part}' for i,part in enumerate(chunks)]
  self.assertEqual(decode(texts,case),[line])
  with self.assertRaises(ValueError):decode(texts[:-1],case)
  texts[-1]=texts[-1][:-5]+'...'
  with self.assertRaises(ValueError):decode(texts,case)

class SubscriptionLifetimeTests(unittest.TestCase):
 @unittest.skipUnless((ROOT/'.local/qc-breadth-v1/asset-source.py').exists(),'Private adapters not distributed')
 def test_unheld_current_and_delayed_targets_do_not_enter_feature_universe(self):
  for case in ['ew_stock','stress','ew_stress']:
   t=ast.parse(generate(case));names=['select_universe','_retained_targets'];fns=[n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name in names]
   scope=dict(MODE='momentum',math=math,Universe=NS(UNCHANGED='unchanged'))
   exec(compile(ast.Module(body=fns,type_ignores=[]),'retention','exec'),scope)
   new,old,pending=map(Symbol,['new','unheld-current','unheld-delayed'])
   s=NS(time=datetime(2020,3,3),_universe_month=None,_universe_calls=0,_fundamental_valid=0,_membership_hash=hashlib.sha256(),_weights={old:1},_delay_weights={pending:1})
   s._retained_targets=lambda:scope['_retained_targets'](s)
   f=NS(has_fundamental_data=True,price=20,dollar_volume=10000,market_cap=100000,symbol=new)
   actual=scope['select_universe'](s,[f]);self.assertEqual(s._selected,[new]);self.assertEqual(set(actual),{new,old,pending},case)
