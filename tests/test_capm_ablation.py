import ast
import hashlib
import json
import unittest
from research.capm_ablation import CASES, build_source, decode_fragments, factorial_effects


class CapmAblationTests(unittest.TestCase):
    def test_passive_selection_audit_needs_no_custom_native_proxy_attributes(self):
        from datetime import datetime
        from types import SimpleNamespace
        import numpy as np
        tree = ast.parse(build_source('c25_on'))
        model = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CapmAlphaRankingUniverseSelectionModel')
        method = next(n for n in model.body if isinstance(n, ast.FunctionDef) and n.name == 'select_pair')
        module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
        audit = {'count': 0, 'digest': hashlib.sha256()}
        namespace = {'np': np, 'SELECTION_AUDIT': audit}
        exec(compile(module, '<selector-test>', 'exec'), namespace)
        class NativeProxy:
            __slots__ = ('utc_time',)
        proxy = NativeProxy()
        proxy.utc_time = datetime(2016, 1, 4, 14, 30)
        values = {'SPY': [.01, .02, -.01], 'A': [.01, .02, -.01], 'B': [.02, .03, 0], 'C': [0, .01, -.02]}
        class TestSymbol(str):
            @property
            def id(self):
                return self
        model_stub = SimpleNamespace(_symbols=[TestSymbol(x) for x in ['A', 'B', 'C']], benchmark='SPY', _get_returns=lambda algorithm, symbol: values[symbol])
        selected = namespace['select_pair'](model_stub, proxy, None)
        self.assertEqual(selected, ['C', 'A'])
        self.assertEqual(audit['count'], 1)
        self.assertNotEqual(audit['digest'].hexdigest(), hashlib.sha256().hexdigest())

    def test_factor_grid_and_ranking_are_fixed(self):
        self.assertEqual(len(CASES),9)
        baseline=None
        for case,(mode,cost,stop) in CASES.items():
            source=build_source(case);tree=ast.parse(source)
            universe=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CapmAlphaRankingUniverseSelectionModel')
            shape=ast.dump(universe)
            baseline=shape if baseline is None else baseline
            self.assertEqual(shape,baseline)
            self.assertIn(f"CASE_ID = '{case}'",source)
            self.assertIn(f"STOP_ENABLED = {stop}",source)
            self.assertIn('ABL_START|',source)
            self.assertLess(len(source),32000)
            if cost=='zero':self.assertIn('security.set_fee_model(ConstantFeeModel(0))',source)
            if mode=='capm' and not stop:self.assertIn('self.set_risk_management(NullRiskManagementModel())',source)
            if mode=='capm' and stop:self.assertIn('self.set_risk_management(MaximumDrawdownPercentPerSecurity(0.01))',source)

    def test_source_alpha_portfolio_execution_calls_preserved(self):
        from research.quantconnect.capm_study import build_source as old
        names={'set_alpha','set_portfolio_construction','set_execution','set_universe_selection'}
        def calls(source):
            return sorted(ast.dump(n) for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in names)
        for case,info in CASES.items():self.assertEqual(calls(build_source(case)),calls(old(info[0])))

    def test_packets_cannot_use_wrong_case_or_study(self):
        payload=dict(study='capm-ablation-v1',case='c0_on',kind='full')
        raw=json.dumps(payload,separators=(',',':'));digest=hashlib.sha256(raw.encode()).hexdigest()[:12]
        row=f'ABL|c0_on|0|0|1|{digest}|{raw}'
        self.assertEqual(decode_fragments([row,row],'c0_on'),[payload])
        with self.assertRaises(ValueError):decode_fragments([row],'c0_off')
        with self.assertRaises(ValueError):decode_fragments([row+'x'],'c0_on')
        with self.assertRaises(ValueError):decode_fragments([row.replace('|0|1|','|0|2|')],'c0_on')

    def test_factorial_contrasts_include_interaction(self):
        values=dict(c0_on=.20,c0_off=.10,cf_on=.15,cf_off=.08,c25_on=-.50,c25_off=.04,s0=.12,sf=.11,s25=.10)
        results={}
        for c,v in values.items():
            m=dict(cagr=v,ret=v,dd=-.2,sharpe=1,calmar=v/.2,annual_calmar=v/.2,uw_fraction=.5,longest_uw=20,longest_uw_days=30)
            results[c]=[dict(kind='full',metrics=m)]+[dict(kind='annual',year=y,metrics=m) for y in range(2016,2026)]
        effects=factorial_effects(results)
        interaction=next(x for x in effects if x['kind']=='full' and x['metric']=='cagr' and x['effect']=='total_cost_stop_interaction')
        self.assertAlmostEqual(interaction['value'],-.64)
        fee=next(x for x in effects if x['kind']=='full' and x['metric']=='cagr' and x['effect']=='fees_minus_zero' and x['stop'])
        self.assertAlmostEqual(fee['value'],-.05)
