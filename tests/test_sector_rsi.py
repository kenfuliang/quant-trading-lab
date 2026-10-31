"""Epoch3 invented-data and guard tests; no historical runs or broker access."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from research.studies.sector_rsi import model, audit, signals
from research.studies.sector_gate import model as parent
from research.sector_corporate_actions import total_return_indexes
from tests.test_sector_selection_model import synthetic_input


class SectorRSITests(unittest.TestCase):
    def test_synthetic_accounts_independent_replay_and_incumbent_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=synthetic_input(root)
            frames,actions=model.load_inputs(bundle)
            for policy in model.POLICIES:
                output=root/policy
                model.save_case(output,frames,actions,policy,5,end='2017-04-28')
                result=audit.replay(bundle,output,policy,5,end='2017-04-28')
                self.assertEqual(result['status'],'passed')
                if policy in ('gate','vol'):
                    old=root/(policy+'-parent')
                    parent.save_case(old,frames,actions,policy,5,end='2017-04-28')
                    for name in ('ledger.csv','trades.csv','summary.json','selections.json','contributions.csv'):
                        self.assertEqual((output/name).read_bytes(),(old/name).read_bytes())
            # Tampering with correlation selection must fail independent audit.
            p=root/'corr/selections.json';rows=json.loads(p.read_text())
            rows[0]['picks']=list(reversed(rows[0]['picks']));p.write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):audit.replay(bundle,root/'corr','corr',5,end='2017-04-28')

    def test_selection_causal_prefix_and_top_six_constraint(self):
        with tempfile.TemporaryDirectory() as tmp:
            frames,actions=model.load_inputs(synthetic_input(Path(tmp)))
            indexes=total_return_indexes(frames,actions);position=280
            picks,scores=model.selections(indexes,'corr',position)
            top=sorted(scores,key=lambda s:(-scores[s]['score'],s))[:6]
            self.assertEqual(picks[0],top[0]);self.assertEqual(len(set(picks)),3)
            self.assertTrue(set(picks).issubset(top))
            for series in indexes.values():series.iloc[position+1:]*=10
            self.assertEqual((picks,scores),model.selections(indexes,'corr',position))

    def test_breadth_prefix_and_independent_daily_states(self):
        dates=pd.bdate_range('2016-01-04',periods=330)
        indexes={s:pd.Series(100*np.exp(np.arange(330)*(.001 if j<7 else -.001)),index=dates)
                 for j,s in enumerate(model.SYMBOLS)}
        actual=signals.breadth_timeline(indexes)
        independent=audit.independent_breadth({s:v.tolist() for s,v in indexes.items()},list(map(str,dates.date)))
        for i in range(200,330):
            self.assertEqual(actual.iloc[i].state,independent[i-1]['state'])
            self.assertEqual(actual.iloc[i].cap,float(independent[i-1]['cap']))
            self.assertEqual(actual.iloc[i].breadth,independent[i-1]['breadth'])
        changed={s:v.copy() for s,v in indexes.items()}
        for series in changed.values():series.iloc[300:]*=.5
        pd.testing.assert_frame_equal(actual.iloc[:300],signals.breadth_timeline(changed).iloc[:300])
        self.assertEqual(actual.iloc[204].state,'green')

    def test_nonfinite_or_zero_volatility_never_changes_universe(self):
        dates=pd.bdate_range('2016-01-04',periods=270)
        indexes={s:pd.Series(np.ones(270)*100,index=dates) for s in model.SYMBOLS}
        with self.assertRaisesRegex(ValueError,'volatility'):model.selections(indexes,'corr',260)
        indexes['XLB'].iloc[20]=np.nan
        with self.assertRaisesRegex(ValueError,'Invalid'):signals.breadth_timeline(indexes)

    def test_frozen_review_requires_both_costs_and_all_guards(self):
        from research.studies.sector_rsi.review import decision
        baseline=dict(calmar=1.,cagr_pct=10.,max_drawdown_pct=10.,uw_sessions=100,uw_days=140)
        rows=[dict(baseline,policy=p,cost_bps=b) for b in (5,10) for p in ('gate','equal','corr')]
        for r in rows:
            if r['policy']=='corr':r.update(calmar=1.2,cagr_pct=11.,max_drawdown_pct=9.,uw_sessions=90,uw_days=130)
        self.assertTrue(decision(rows,'corr','equal')['fixed_target_passed'])
        rows[-1]['cagr_pct']=9.
        outcome=decision(rows,'corr','equal')
        self.assertFalse(outcome['fixed_target_passed'])
        self.assertFalse(outcome['contexts']['10']['checks']['cagr_not_lower'])
        self.assertFalse(outcome['independent_alpha_established'])


if __name__=='__main__':unittest.main()
