"""Supervisor failure injection only: no strategy, prices or child process runs."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from subprocess import TimeoutExpired
from research import risk_gate_ablation as ab

class TimeoutTests(unittest.TestCase):
 def test_timeout_counts_active_attempt_and_never_launches_next(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);state=root/'state.json';plan=root/'plan.json';plan.write_text('{}')
   state.write_text(json.dumps(dict(actual_financial_attempts=12,failed_attempts=2,attempts=[])))
   previous=os.getcwd()
   try:
    os.chdir(root)
    with patch.object(ab,'PLAN',plan),patch.object(ab.study,'STATE',state),patch.object(ab,'validate'),patch.object(ab.study,'digest',return_value='a'*64),patch.object(ab.subprocess,'run',side_effect=TimeoutExpired('synthetic',.01)) as child:
     with self.assertRaises(TimeoutExpired):ab.execute({})
   finally:os.chdir(previous)
   saved=json.loads(state.read_text())
   self.assertEqual(child.call_count,1)
   self.assertEqual(saved['actual_financial_attempts'],13)
   self.assertEqual(saved['failed_attempts'],3)
   self.assertEqual(saved['followup_attempts'][0]['status'],'failed')
   self.assertTrue(all(x['status']=='reserved' for x in saved['followup_attempts'][1:]))

class RecoveryTimeoutTests(unittest.TestCase):
 def test_recovery_timeout_preserves_failure_before_next_case(self):
  from datetime import datetime,timezone,timedelta
  from research import risk_gate_recovery2 as rec
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);state=root/'state.json';plan=root/'plan.json';plan.write_text('{}')
   state.write_text(json.dumps(dict(actual_financial_attempts=2,failed_attempts=2,attempts=[dict(status='failed') for _ in range(2)]+[dict(status='not_started_due_stop') for _ in range(10)])))
   deadline=datetime.now(timezone.utc)+timedelta(seconds=900)
   p=dict(recovery=dict(new_case_indices=list(range(2,12)),original_deadline_utc=deadline.isoformat(),ema_source='saved/5_ema'),cases=[dict(id=str(i)) for i in range(12)])
   previous=os.getcwd()
   try:
    os.chdir(root)
    with patch.object(rec,'PLAN',plan),patch.object(rec.previous,'ORIGINAL',plan),patch.object(rec.study,'STATE',state),patch.object(rec,'bounds',return_value=deadline),patch.object(rec.study,'validate'),patch.object(rec,'verify_artifacts'),patch.object(rec.study,'digest',return_value='a'*64),patch.object(rec.subprocess,'run',side_effect=TimeoutExpired('synthetic',.01)) as child:
     with self.assertRaises(TimeoutExpired):rec.execute(p)
   finally:os.chdir(previous)
   saved=json.loads(state.read_text())
   self.assertEqual(child.call_count,1)
   self.assertEqual(saved['actual_financial_attempts'],3)
   self.assertEqual(saved['failed_attempts'],3)
   self.assertEqual(saved['attempts'][2]['status'],'failed')
   self.assertTrue(all(x['status']=='not_started_due_stop' for x in saved['attempts'][3:]))
