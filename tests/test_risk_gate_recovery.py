import unittest
from datetime import datetime,timezone
from research.risk_gate_recovery import eligible

class RecoveryTests(unittest.TestCase):
    def state(self):return dict(status='stopped_checker_repaired_not_rerun',actual_financial_attempts=1,started_utc='2026-10-25T18:46:50+00:00',attempts=[dict(id='5_hold',status='failed')]+[dict(status='not_started_due_stop') for _ in range(11)])
    def test_original_deadline_and_no_failed_retry(self):
        s=self.state();d,r=eligible(s,dict(wall_seconds=900),datetime(2026,10,25,18,50,tzinfo=timezone.utc))
        self.assertEqual(d.isoformat(),'2026-10-25T19:01:50+00:00');self.assertEqual(r,710)
        with self.assertRaises(ValueError):eligible(s,dict(wall_seconds=900),datetime(2026,10,25,19,2,tzinfo=timezone.utc))
        for key,value in [('actual_financial_attempts',2),('status','recovery_running')]:
            s=self.state();s[key]=value
            with self.assertRaises(ValueError):eligible(s,dict(wall_seconds=900),datetime(2026,10,25,18,50,tzinfo=timezone.utc))
        s=self.state();s['attempts'][1]['status']='failed'
        with self.assertRaises(ValueError):eligible(s,dict(wall_seconds=900),datetime(2026,10,25,18,50,tzinfo=timezone.utc))
