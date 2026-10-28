import unittest
from datetime import datetime,timezone
from research.studies.spy.risk_gate_recovery2 import bounds
class Recovery2Tests(unittest.TestCase):
 def test_two_failures_are_counted_and_deadline_unchanged(self):
  s=dict(status='recovery_failed_no_further_launch',actual_financial_attempts=2,failed_attempts=2,started_utc='2026-10-25T18:46:50+00:00',attempts=[dict(status='failed')]*2+[dict(status='not_started_due_stop')]*10)
  self.assertEqual(bounds(s,{},datetime(2026,10,25,18,58,tzinfo=timezone.utc)).isoformat(),'2026-10-25T19:01:50+00:00')
  with self.assertRaises(ValueError):bounds(s,{},datetime(2026,10,25,19,2,tzinfo=timezone.utc))
  s['actual_financial_attempts']=3
  with self.assertRaises(ValueError):bounds(s,{},datetime(2026,10,25,18,58,tzinfo=timezone.utc))
