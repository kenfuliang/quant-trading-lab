import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research import gate_robustness as study


class GateRobustnessTests(unittest.TestCase):
    def fixture(self):
        price = np.r_[np.linspace(100, 150, 250), np.linspace(150, 85, 50),
                      np.linspace(85, 160, 100)]
        return pd.DataFrame(dict(open=price, low=price-1, high=price+1, close=price),
                            index=pd.bdate_range('2000-01-03', periods=len(price)))

    def test_only_decisions_delayed_and_no_future_leak(self):
        raw = self.fixture()
        frames, _ = study.frozen_frames(raw)
        changed = raw.copy()
        changed.iloc[320:] *= .5
        changed_frames, _ = study.frozen_frames(changed)
        for name in ('gate_ema', 'ema'):
            original = frames[name]
            delayed = study.delayed_frame(original, 1)
            pd.testing.assert_frame_equal(delayed[['open', 'low', 'close']],
                                          original[['open', 'low', 'close']])
            np.testing.assert_array_equal(delayed.intended_target.iloc[1:], original.intended_target.iloc[:-1])
            pd.testing.assert_frame_equal(delayed.drop(columns=['open', 'low', 'close']).iloc[:322],
                study.delayed_frame(changed_frames[name], 1).drop(columns=['open', 'low', 'close']).iloc[:322])
            pd.testing.assert_frame_equal(study.delayed_frame(original, 0), original)

    def test_standing_control_and_budget(self):
        frames, _ = study.frozen_frames(self.fixture())
        with self.assertRaises(ValueError):
            study.delayed_frame(frames['buy_hold_entry_only'], 1)
        with self.assertRaises(ValueError):
            study.delayed_frame(frames['ema'], 2)
        self.assertEqual(len(study.CASES), 9)
        self.assertEqual(len({c['id'] for c in study.CASES}), 9)
        self.assertTrue(all(c['signal_delay'] == 0 for c in study.CASES
                            if c['rule'] == 'buy_hold_entry_only'))

    def test_joint_claim_cannot_hide_duration_or_growth_loss(self):
        control = dict(return_pct=8., drawdown_pct=-29., duration=531)
        good = dict(return_pct=8.7, drawdown_pct=-18., duration=513)
        self.assertTrue(study.joint_claim(good, control)['passed'])
        self.assertFalse(study.joint_claim(good | dict(duration=532), control)['passed'])
        self.assertFalse(study.joint_claim(good | dict(return_pct=7.9), control)['passed'])
        self.assertFalse(study.joint_claim(control, control)['passed'])

    def test_invalid_bounds_stop_before_inputs(self):
        plan = dict(schema='spy-gate-robustness-v1', cases=study.CASES,
                    max_attempts=10, wall_seconds=900, financial_workers=1, automatic_retries=0)
        with self.assertRaisesRegex(ValueError, 'bounds'):
            study.preflight(plan)

    def test_failed_attempt_preserved_and_no_replay(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                planfile = Path('plan.json')
                planfile.write_text('{}')
                failure = subprocess.CompletedProcess([], 1, 'partial', 'failed deliberately')
                with patch.object(study, 'PLAN', planfile), patch.object(study, 'preflight'), \
                     patch.object(study.subprocess, 'run', return_value=failure) as launch:
                    with self.assertRaises(RuntimeError):
                        study.execute(dict(wall_seconds=900))
                    out = Path('.local/gate-robustness') / study.old.digest(planfile)[:16]
                    state = json.loads((out / 'state.json').read_text())
                    self.assertEqual(state['actual_attempts'], 1)
                    self.assertEqual(state['attempts'][0]['status'], 'failed')
                    self.assertEqual(state['attempts'][1]['status'], 'reserved')
                    self.assertEqual(state['status'], 'stopped_inconclusive_no_retry')
                    self.assertTrue((out / 'base_gate_ema.log').exists())
                    study.verify_artifacts(out)
                    with self.assertRaises(FileExistsError):
                        study.execute(dict(wall_seconds=900))
                    self.assertEqual(launch.call_count, 1)
            finally:
                os.chdir(original_cwd)

    def test_timeout_consumes_attempt_and_preserves_manifest(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                planfile = Path('plan.json')
                planfile.write_text('{}')
                with patch.object(study, 'PLAN', planfile), patch.object(study, 'preflight'), \
                     patch.object(study.subprocess, 'run', side_effect=subprocess.TimeoutExpired('child', 900)):
                    with self.assertRaises(subprocess.TimeoutExpired):
                        study.execute(dict(wall_seconds=900))
                    out = Path('.local/gate-robustness') / study.old.digest(planfile)[:16]
                    state = json.loads((out / 'state.json').read_text())
                    self.assertEqual(state['actual_attempts'], 1)
                    self.assertEqual(state['attempts'][0]['status'], 'failed')
                    study.verify_artifacts(out)
            finally:
                os.chdir(original_cwd)


if __name__ == '__main__':
    unittest.main()
