"""Evidence-integrity and temporal metric checks; no cloud calls."""
import ast
import hashlib
import json
import unittest
from research.capm_review import decode_fragments
from research.quantconnect.capm_study import build_source, ORIGINAL
from research.quantconnect.sector_metrics import summarize_path


def fragments(payload):
    raw = json.dumps(payload, separators=(',', ':'))
    chunks = [raw[i:i+25] for i in range(0, len(raw), 25)]
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return [f'CAP|spy|0|{i}|{len(chunks)}|{digest}|{c}' for i,c in enumerate(chunks)]


class CapmReviewTests(unittest.TestCase):
    def test_missing_and_corrupt_fragments_fail_closed(self):
        rows = fragments(dict(study='capm-spy-v1', case='spy', kind='full'))
        self.assertEqual(decode_fragments(rows+rows, 'spy')[0]['kind'], 'full')
        with self.assertRaisesRegex(ValueError, 'Missing'):
            decode_fragments(rows[:-1], 'spy')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            decode_fragments(rows[:-1]+[rows[-1]+'x'], 'spy')

    def test_identity_cannot_be_borrowed_from_different_study(self):
        with self.assertRaisesRegex(ValueError, 'Study/case'):
            decode_fragments(fragments(dict(study='other',case='spy')), 'spy')

    def test_framework_signal_models_unchanged(self):
        original = ast.parse(ORIGINAL.read_text())
        built = ast.parse(build_source('capm'))
        def get_model(tree):
            return next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CapmAlphaRankingUniverseSelectionModel')
        self.assertEqual(ast.dump(get_model(original)), ast.dump(get_model(built)))
        old_init = next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name=='CapmAlphaRankingFrameworkAlgorithm').body[-1]
        new_cls = next(n for n in built.body if isinstance(n, ast.ClassDef) and n.name=='CapmAlphaRankingFrameworkAlgorithm')
        new_init = next(n for n in new_cls.body if isinstance(n, ast.FunctionDef) and n.name=='initialize')
        names = {'set_alpha','set_portfolio_construction','set_execution','set_risk_management'}
        def calls(node):
            return sorted(ast.dump(n) for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in names)
        self.assertEqual(calls(old_init),calls(new_init))
        self.assertIn('MaximumDrawdownPercentPerSecurity(0.01)', build_source('capm'))
        self.assertIn("CASE = 'probe'", build_source('probe'))
        with self.assertRaises(ValueError):
            build_source('unknown')

    def test_underwater_cross_year_and_annual_reset(self):
        path = [('2020-12-30',110),('2020-12-31',100),('2021-01-04',105),('2021-01-05',111)]
        full = summarize_path(path,100,'2020-12-29')
        annual = summarize_path(path[2:],100,'2020-12-31')
        self.assertEqual(full['longest_uw'], 2)
        self.assertEqual(annual['longest_uw'], 0)
        self.assertEqual(full['uw_fraction'], 0.5)
        self.assertEqual(full['longest_uw_days'], 5)

    def test_aggregate_audit_detects_failed_native_identity(self):
        from research.capm_review import audit_metrics
        rows, annual = [], []
        opening, anchor, nav = 300000.0, '2015-12-31', 300000.0
        for year in range(2016,2026):
            dates = [f'{year}-01-04',f'{year}-12-31']
            chunk = [(dates[0],nav*1.05),(dates[1],nav*1.05*.99)]
            annual.append(dict(study='capm-spy-v1',case='spy',kind='annual',year=year,metrics=summarize_path(chunk,opening,anchor)))
            rows.extend(chunk)
            opening, anchor = chunk[-1][1],chunk[-1][0]
            nav = opening
        full = dict(study='capm-spy-v1',case='spy',kind='full',metrics=summarize_path(rows,300000.0,'2015-12-31'),audit=dict(first='2016-01-04',last='2025-12-31',calendar_hash='fixture',rejects=0,pending=0,native_book_residual=0,native_fee_residual=0,last_mark_residual=0,fee_models=['InteractiveBrokersFeeModel'],fees=20,interest=0,min_cash=1000,max_gross=.99))
        self.assertTrue(audit_metrics(annual+[full])['passed'])
        full['audit']['native_book_residual']=200000
        with self.assertRaisesRegex(ValueError,'accounting'):
            audit_metrics(annual+[full])
        full['audit']['native_book_residual']=0
        annual[0]['metrics']['ret']+=.01
        with self.assertRaises(ValueError):
            audit_metrics(annual+[full])
