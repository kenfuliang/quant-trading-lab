"""Offline observer boundaries and holdings attribution; no copied strategy fixture."""
import ast,json,math,statistics
from pathlib import Path
from types import SimpleNamespace,MethodType
from unittest.mock import patch
import unittest
from research.quantconnect import qc504_audit as audit
from research.quantconnect.sector_metrics import summarize_path

class Qc504AuditTests(unittest.TestCase):
    def test_observation_code_has_no_order_or_target_calls(self):
        tree=ast.parse(Path('research/quantconnect/qc504_audit.py').read_text())
        denied={'market_order','market_on_open_order','set_holdings','liquidate','set_cash','set_start_date','set_end_date'}
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):self.assertNotIn(n.func.attr,denied)

    def test_asset_book_does_not_double_count_dividends_or_estimated_exit_fees(self):
        close_fee_flags=[]
        class Holding:
            net_profit=400.;total_fees=10.;total_dividends=50.
            def total_close_profit(self,include_fees):
                close_fee_flags.append(include_fees)
                return 95. if include_fees else 100.
        class Portfolio(dict):
            total_portfolio_value=10500.;total_fees=10.
        rows=[]
        obj=SimpleNamespace(_audit_curve=[('2020-01-02',9500.),('2020-12-31',10500.)],
            _audit_rejects=0,_audit_fills=2,_audit_other_fills=0,_audit_max_gross=1.02,
            _audit_min_cash=-100.,_audit_sessions=SimpleNamespace(hexdigest=lambda:'fixture'),
            _audit_sleeves={k:{} for k in ('t10','t11','s2','s3')},_syms={'ETF':'symbol'},
            portfolio=Portfolio(symbol=Holding()),_audit_emit=rows.append)
        with patch.multiple(audit,json=json,math=math,summarize_path=summarize_path,AUDIT_CASE='recent',AUDIT_START_YEAR=2020,create=True):
            audit.audit_end(obj)
        asset=next(r for r in rows if r['kind']=='assets')
        self.assertEqual(close_fee_flags,[False]);self.assertEqual(asset['values'],[['ETF',500.,10.]])
        self.assertEqual(asset['residual_usd'],0.)
        self.assertEqual(next(r for r in rows if r['kind']=='overall')['min_cash'],-100.)

    def test_log_limit_fails_before_silently_truncating(self):
        messages=[]
        obj=SimpleNamespace(_audit_log_bytes=9290,log=messages.append)
        with patch.object(audit,'json',json,create=True):
            with self.assertRaises(ValueError):audit.audit_emit(obj,{'study':'qc504-v1'})
        self.assertEqual(messages,[])

if __name__=='__main__':unittest.main()
