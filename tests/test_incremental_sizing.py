import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from research import incremental_sizing as s


class IncrementalSizingTests(unittest.TestCase):
    def fixture(self):
        v=100+np.arange(450)*.08+np.sin(np.arange(450)/4)*2
        return pd.DataFrame(dict(open=v,high=v+1,low=v-1,close=v),index=pd.bdate_range('2000-01-03',periods=len(v)))

    def test_causal_single_lag_and_unmodified_parent(self):
        raw=self.fixture();frames,decisions=s.build_frames(raw)
        changed=raw.copy();changed.iloc[350:]*=1.5
        other,_=s.build_frames(changed)
        pd.testing.assert_frame_equal(frames['continuous_ema'].iloc[:350].drop(columns=['open','low','close']),other['continuous_ema'].iloc[:350].drop(columns=['open','low','close']))
        earlier,_=s.build_frames(raw.iloc[:350]);pd.testing.assert_frame_equal(earlier['continuous_ema'],frames['continuous_ema'].iloc[:350])
        sigma=raw.close.pct_change(fill_method=None).iloc[300-20:300].std(ddof=1)*np.sqrt(252)
        self.assertAlmostEqual(decisions.sigma20.iloc[300],sigma)
        self.assertEqual(decisions.available_at.iloc[300],raw.index[299].strftime('%Y-%m-%d'))
        base,_=s.discrete_frames(raw)
        pd.testing.assert_frame_equal(base['gate_ema'],frames['discrete_ema'])
        pd.testing.assert_frame_equal(base['ema'],frames['ema'])
        np.testing.assert_allclose(frames['half_ema'].intended_target,frames['ema'].base_target*.5)

    def test_zero_volatility_has_zero_continuous_target(self):
        raw=self.fixture();raw.loc[:,'open']=raw.loc[:,'close']=100.;raw.loc[:,'high']=101.;raw.loc[:,'low']=99.
        frames,d=s.build_frames(raw)
        self.assertTrue(frames['continuous_ema'].allocation_factor.eq(0).all())
        self.assertTrue(d.continuous_cap.eq(0).all())

    def test_primary_requires_both_contexts_and_shorter_duration(self):
        rows={c['id']:dict(return_pct=8.,drawdown_pct=-20.,duration=500) for c in s.CASES}
        for cost in (5,10):rows[f'{cost}bp_continuous_ema'].update(duration=499)
        self.assertTrue(s.primary_claim(rows)['primary_pass'])
        rows['10bp_continuous_ema']['duration']=500
        self.assertFalse(s.primary_claim(rows)['primary_pass'])
        rows['10bp_continuous_ema'].update(duration=499,drawdown_pct=-20.01)
        self.assertFalse(s.primary_claim(rows)['primary_pass'])

    def test_invalid_bounds_rejected_before_input_access(self):
        p=dict(cycle=s.CYCLE,cases=s.CASES,max_attempts=9,wall_seconds=900,financial_workers=1,automatic_retries=0)
        with self.assertRaisesRegex(ValueError,'bounds'):s.preflight(p)

    def test_failure_preserved_consumes_attempt_and_cannot_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'run';plan=Path(temp)/'plan.json';plan.write_text('{}')
            failure=subprocess.CompletedProcess([],1,'partial output','synthetic failure')
            with patch.object(s,'ROOT',root),patch.object(s,'PLAN',plan),patch.object(s,'preflight'),patch.object(s.subprocess,'run',return_value=failure) as launch:
                with self.assertRaises(RuntimeError):s.execute(dict(wall_seconds=900))
                state=json.loads((root/'state.json').read_text())
                self.assertEqual(state['actual_attempts'],1);self.assertEqual(state['attempts'][0]['status'],'failed')
                self.assertEqual(state['status'],'closed-inconclusive-no-retry')
                self.assertTrue((root/'5bp_ema.log').exists());s.verify_artifacts(root)
                with self.assertRaises(FileExistsError):s.execute(dict(wall_seconds=900))
                self.assertEqual(launch.call_count,1)
