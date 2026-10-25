"""Adversarial synthetic accounting boundaries; no historical studies launched."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research import bounded_study as study
from research.leveraged_spy import FinancingModel


def fixture():
    idx=pd.Index(['2025-01-02','2025-01-03'],name='date')
    frame=pd.DataFrame({'open':100.,'low':99.,'close':100.,'want_long':False},index=idx)
    curve=pd.DataFrame({'cash':300000.,'shares':0,'close':100.,'equity_usd':300000.,
                        'effective_target_leverage':1.,'financing_usd':0.,'dividend_usd':0.,
                        'commission_usd':0.,'slippage_usd':0.,'max_checked_leverage':0.,
                        'min_margin_buffer_pct':100.,'forced_liquidations':0,
                        'initial_margin_rejections':0,'halted':False,'insolvent':False},index=idx)
    return frame,curve,pd.DataFrame()


class AdversarialStudyTests(unittest.TestCase):
    def test_finite_all_cash_boundary_and_no_trade_frame(self):
        study.validate_financial_outputs(*fixture())

    def test_nan_infinity_and_nonnumeric_fields_are_rejected(self):
        for field in ('cash','equity_usd','shares','financing_usd','dividend_usd','min_margin_buffer_pct'):
            for value in (float('nan'),float('inf')):
                f,c,t=fixture();c[field]=c[field].astype(float);c.loc[c.index[-1],field]=value
                with self.assertRaisesRegex(ValueError,'Nonfinite'):study.validate_financial_outputs(f,c,t)
        f,c,t=fixture();c['cash']='300000'
        with self.assertRaises(ValueError):study.validate_financial_outputs(f,c,t)

    def test_surplus_missing_duplicate_or_shuffled_dates_rejected(self):
        for kind in ('extra','missing','duplicate','shuffle'):
            f,c,t=fixture()
            if kind=='extra':c.loc['2025-01-06']=c.iloc[-1]
            elif kind=='missing':c=c.iloc[:1]
            elif kind=='duplicate':c=pd.concat([c,c.iloc[:1]])
            else:c=c.iloc[::-1]
            with self.assertRaisesRegex(ValueError,'coverage'):study.validate_financial_outputs(f,c,t)

    def test_unverified_extra_trade_date_and_nonfinite_trade_cash_rejected(self):
        for date,cash in [('2025-01-06',1.),('2025-01-02',float('nan'))]:
            f,c,_=fixture()
            t=pd.DataFrame([{'date':date,'delta':1,'fill_price':100.,'mark':100.,'reason':'rebalance','cash_after':cash,'shares_after':1}])
            with self.assertRaises(ValueError):study.validate_financial_outputs(f,c,t)

    def test_boolean_flags_and_integer_quantities_are_explicit(self):
        f,c,t=fixture();c['halted']='False'
        with self.assertRaisesRegex(ValueError,'booleans'):study.validate_financial_outputs(f,c,t)
        f,c,t=fixture();c['shares']=.5
        with self.assertRaisesRegex(ValueError,'integers'):study.validate_financial_outputs(f,c,t)

    def _mock_plan(self):
        return {'plan_id':'adversarial-no-market-study','evaluation':{'start':'2025-01-02','end':'2025-01-03'},
                'financing_model':asdict(FinancingModel()),'cases':[{'case_id':'flat','strategy_id':2,'exposure':1}]}

    def test_wrapper_rejects_corrupt_curve_before_legacy_audit_and_preserves_failure(self):
        f,c,t=fixture();c.loc[c.index[-1],'equity_usd']=np.nan
        raw=f.copy();raw.index=pd.to_datetime(raw.index)
        p=self._mock_plan()
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'preflight',return_value=(p,raw,{})), \
             patch.object(study,'_verify_inputs'),patch.object(study,'build_case_frame',return_value=raw), \
             patch.object(study,'simulate',return_value=(c,t)),patch.object(study,'reconcile') as audit:
            with self.assertRaisesRegex(ValueError,'Nonfinite'):study.run_plan(p,Path(tmp))
            audit.assert_not_called()
            saved=json.loads(next(Path(tmp).glob('*/manifest.json')).read_text())
            self.assertEqual(saved['status'],'failed')
            self.assertIn('flat/signal.csv',saved['artifact_hashes'])

    def test_cache_rechecks_numeric_outputs_even_with_matching_manifest_hash(self):
        f,c,t=fixture();raw=f.copy();raw.index=pd.to_datetime(raw.index);p=self._mock_plan()
        with tempfile.TemporaryDirectory() as tmp,patch.object(study,'preflight',return_value=(p,raw,{})), \
             patch.object(study,'_verify_inputs'),patch.object(study,'build_case_frame',return_value=raw), \
             patch.object(study,'simulate',return_value=(c,t)):
            out=study.run_plan(p,Path(tmp));directory=Path(out['directory'])
            bad=c.copy();bad.loc[bad.index[-1],'cash']=np.nan
            bad.to_csv(directory/'flat/ledger.csv',index_label='date')
            m=json.loads((directory/'manifest.json').read_text())
            m['artifact_hashes']['flat/ledger.csv']=study.digest(directory/'flat/ledger.csv')
            (directory/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'Nonfinite'):study.run_plan(p,Path(tmp))

    def test_current_day_price_change_cannot_change_already_lagged_mixture_target(self):
        idx=pd.date_range('2004-01-01',periods=280,freq='B')
        close=100+np.sin(np.arange(280)/4)+np.arange(280)*.01
        raw=pd.DataFrame({'open':close,'high':close+1,'low':close-1,'close':close,'volume':1000},index=idx)
        case={'components':[{'strategy_id':2,'weight':.5},{'strategy_id':11,'weight':.5}]}
        before=study.build_case_frame(raw,case)
        changed=raw.copy();changed.loc[idx[270],['open','high','low','close']]*=2
        after=study.build_case_frame(changed,case)
        pd.testing.assert_series_equal(before.allocation_factor.iloc[:271],after.allocation_factor.iloc[:271])


if __name__=='__main__':unittest.main()
