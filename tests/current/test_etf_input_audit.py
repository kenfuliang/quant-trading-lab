import copy,unittest
import pandas as pd
from research.evaluation.etf_input_audit import audit_chart

class InputAuditTests(unittest.TestCase):
 def payload(self):
  dates=pd.date_range('2004-12-01',periods=3,freq='B',tz='America/New_York')+pd.Timedelta(hours=9,minutes=30)
  q=dict(open=[100]*3,high=[101]*3,low=[99]*3,close=[100]*3,volume=[100]*3)
  return dict(chart=dict(error=None,result=[dict(meta=dict(symbol='SPY',currency='USD',instrumentType='ETF',exchangeTimezoneName='America/New_York',dataGranularity='1d'),timestamp=[int(t.timestamp()) for t in dates],indicators=dict(quote=[q],adjclose=[dict(adjclose=[90]*3)]),events=dict(dividends={'x':dict(date=int(dates[1].timestamp()),amount=1)}))]))
 def test_structure_does_not_establish_rights_or_cash(self):
  r,f=audit_chart(self.payload(),'SPY');self.assertEqual(len(f),3);self.assertFalse(r['payment_dates_present']);self.assertTrue(r['rights'].startswith('unverified'))
 def test_rejects_identity_preinception_duplicate_and_nonfinite(self):
  for mutate in [lambda r:r['meta'].update(symbol='IEF'),lambda r:r['timestamp'].__setitem__(0,0),lambda r:r['timestamp'].__setitem__(1,r['timestamp'][0]),lambda r:r['indicators']['quote'][0]['close'].__setitem__(0,float('nan')),lambda r:r['indicators']['quote'][0]['low'].__setitem__(0,200)]:
   p=self.payload();mutate(p['chart']['result'][0])
   with self.assertRaises(ValueError):audit_chart(p,'SPY')
