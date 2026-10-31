"""Invented states and paths only; no original strategy execution or market data."""
from copy import deepcopy
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from research.studies.t11_reproduction.contracts import decision,funding,nav_check
from research.studies.t11_reproduction.reference import load_cells,legacy_metrics,compare_path

class TestT11Reproduction(unittest.TestCase):
    def fixture(self):
        return {'session':'2020-01-03','input_session':'2020-01-03','observed_through_utc':'2020-01-03T21:00:00Z',
            'available_at_utc':'2020-01-03T21:00:01Z','decision_at_utc':'2020-01-03T21:00:02Z','earliest_execution_session':'2020-01-06',
            'state':'yellow','cap':'.5','base_weights':{'AAA':'1'},'target_weights':{'AAA':'.45'},
            'controller_phase':'reduce_pending','positions':{'AAA':2},'pending_order_ids':['order-1'],
            'policy_source_sha256':'a'*64,'input_identity_sha256':'b'*64}
    def test_staged_red_can_hold_shares_awaiting_reduction(self):
        r=self.fixture();r.update(state='red',cap=0,target_weights={})
        self.assertEqual(decision(r,['2020-01-03','2020-01-06'])['status'],'contract_valid')
    def test_future_input_or_same_day_execution_rejected(self):
        for k,v in [('available_at_utc','2020-01-04T21:00:00Z'),('earliest_execution_session','2020-01-03')]:
            r=self.fixture();r[k]=v
            with self.assertRaises(ValueError):decision(r,['2020-01-03','2020-01-06'])
    def test_scale_and_identity_changes_rejected(self):
        for k,v in [('target_weights',{'AAA':'.9'}),('policy_source_sha256','short')]:
            r=self.fixture();r[k]=v
            with self.assertRaises(ValueError):decision(r,['2020-01-03','2020-01-06'])
    def test_funding_weekend_and_no_credit_interest(self):
        self.assertEqual(funding('-12000','2020-01-03','2020-01-06'),D(6))
        self.assertEqual(funding('12000','2020-01-03','2020-01-06'),0)
        with self.assertRaises(ValueError):funding('NaN','2020-01-03','2020-01-06')
    def test_nav_residual_and_receivable_not_free_cash(self):
        r={'cash_usd':'100','receivables_usd':'2','nav_usd':'302','positions':{'AAA':2},'marks_usd':{'AAA':100}}
        self.assertEqual(nav_check(r)['residual_usd'],'0')
        r['nav_usd']='304'
        with self.assertRaises(ValueError):nav_check(r)
    def test_old_duration_retained_without_claiming_daily_parity(self):
        rows=[{'session':d,'nav_usd':v} for d,v in [('2020-01-02',9000),('2020-01-03',10000),('2020-01-06',11000)]]
        s=legacy_metrics(rows);self.assertEqual(s['longest_uw'],1)
        match=compare_path(s,rows,account_audit_passed=True,policy_audit_passed=True)
        self.assertTrue(match['aggregate_match']);self.assertFalse(match['daily_parity']);self.assertFalse(match['full_reproduction_eligible'])
        self.assertEqual(compare_path(s,None)['status'],'daily_reference_missing')
        changed=deepcopy(rows);changed[-1]['nav_usd']=10001
        self.assertFalse(compare_path(s,changed)['aggregate_match'])
    def test_duplicate_dates_and_nonfinite_path_fail(self):
        for rows in [[{'session':'2020-01-02','nav_usd':'NaN'}],[{'session':'2020-01-02','nav_usd':10000}]*2]:
            with self.assertRaises(ValueError):legacy_metrics(rows)
    def test_reference_cells_reject_duplicate_overall(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cells.json';p.write_text(json.dumps([json.dumps({'kind':'overall','n':3})]))
            self.assertEqual(load_cells(p)[0]['n'],3)
            p.write_text(json.dumps([{'kind':'overall'},{'kind':'overall'}]))
            with self.assertRaises(ValueError):load_cells(p)

    def test_observation_date_and_next_open_are_causal(self):
        for change in [dict(observed_through_utc='2020-01-02T21:00:00Z'),dict(decision_at_utc='2020-01-06T14:30:00Z')]:
            r=self.fixture();r.update(change)
            with self.assertRaises(ValueError):decision(r,['2020-01-03','2020-01-06'])

    def test_readiness_requires_original_source_hash_and_never_enables_finance(self):
        import hashlib
        from research.studies.t11_reproduction.readiness import inspect
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);private=root/'.local/qc504-t11-gate-v1';private.mkdir(parents=True)
            plans=root/'research/plans';plans.mkdir(parents=True)
            code='class QuadEnsemble:\n    def _t11_test(self):\n        return 1\n    def initialize(self):\n        all_tickers=["SPY","XLK","XLF"]\n'
            sh=hashlib.sha256(code.encode()).hexdigest()
            (plans/'qc504-t11-gate-v1.json').write_text(json.dumps({'source_hashes':{'t11':sh,'gated_t11':sh}}))
            for case in ('t11','gated_t11'):
                (private/f'{case}-source.py').write_text(code)
                summaries=[{'kind':'overall','n':1508}]+[{'kind':'annual','year':str(y)} for y in range(2020,2026)]
                (private/f'{case}-summary-cells.json').write_text(json.dumps(summaries))
            qualified=root/'data/qualified/alpaca-sector-etfs-2016-2025-v1-issuer-v2';qualified.mkdir(parents=True)
            prices=root/'invented-prices.json';prices.write_text(json.dumps([{'symbol':s} for s in ['SPY','XLK','XLF']]))
            (qualified/'inputs.json').write_text(json.dumps({'files':{'prices':{'path':'invented-prices.json','sha256':hashlib.sha256(prices.read_bytes()).hexdigest()}}}))
            result=inspect(root);self.assertEqual(len(result['universe']['missing_decision_symbols']),21)
            self.assertEqual(result['financial_runs'],0);self.assertFalse(result['financial_adapter_enabled'])
            (private/'t11-source.py').write_text(code+'\n# changed\n')
            with self.assertRaisesRegex(ValueError,'strategy changed'):inspect(root)
