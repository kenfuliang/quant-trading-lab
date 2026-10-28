import unittest
from decimal import Decimal
from research.evaluation.etf_readiness_probe import reference_fills,split_signal_reference
from research.evaluation.etf_readiness_rounding_probe import affordable_delta

class ReadinessProofTests(unittest.TestCase):
 def test_fee_boundary_and_share_rounding(self):
  self.assertEqual(affordable_delta(300,100,1,3),2)
  self.assertEqual(affordable_delta(301,100,1,3),3)
  self.assertEqual(affordable_delta(70,25,1,3),2)
  self.assertEqual(affordable_delta(.5,100,1,1),0)
  for args in [(-1,100,1,2),(100,0,1,2),(100,10,1,1.5),(float('nan'),10,1,2)]:
   with self.assertRaises(ValueError):affordable_delta(*args)
 def test_split_and_payment_signal_not_double_counted(self):
  self.assertEqual([Decimal(x) for x in split_signal_reference()],[Decimal(100),Decimal(104),Decimal(104),Decimal(104),Decimal(104)])
 def test_independent_cash_rejects_overspend(self):
  fills=[dict(symbol='SPY',side='BUY',quantity='10',price='100.00',commission='1')]
  with self.assertRaises(AssertionError):reference_fills(fills,[])
