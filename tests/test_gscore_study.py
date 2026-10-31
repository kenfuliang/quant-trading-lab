import ast
from collections import deque
from datetime import datetime
from types import SimpleNamespace as NS
import hashlib
import json
import statistics
import unittest
from research.gscore_study import ORIGINAL, ORIGINAL_SHA, CASES, build_source, source_selector, decode_fragments


class GscoreStudyTests(unittest.TestCase):
    def test_pinned_grant_and_score_math_unchanged(self):
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),ORIGINAL_SHA)
        self.assertIn('Apache License',ORIGINAL.read_text())
        original=ast.parse(ORIGINAL.read_text())
        old=next(n for n in ast.walk(original) if isinstance(n,ast.FunctionDef) and n.name=='compute_g_score')
        new=next(n for n in ast.walk(source_selector()) if isinstance(n,ast.FunctionDef) and n.name=='compute_g_score')
        self.assertEqual(ast.dump(old),ast.dump(new))
        for name in ['sorted_by_BM','ratioDicts_medians','g_scores']:
            assignment=lambda tree:next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id==name)
            self.assertEqual(ast.dump(assignment(original)),ast.dump(assignment(source_selector())))

    def test_known_quality_stock_passes_low_book_quartile(self):
        node=source_selector();module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
        ns={'stat':statistics,'deque':deque,'Universe':NS(Unchanged='UNCHANGED'),'MorningstarSectorCode':NS(Technology=311)}
        exec(compile(module,'<licensed-selector-test>','exec'),ns)
        def stock(i):
            tech=i<4;good=i==0
            year=.2 if good else .1;cf=.4 if good else .05
            return NS(Symbol='T'+str(i),AssetClassification=NS(MorningstarSectorCode=311 if tech else 200),OperationRatios=NS(ROA=NS(ThreeMonths=.02 if good else .1,OneYear=year)),MarketCap=100,FinancialStatements=NS(BalanceSheet=NS(TotalAssets=NS(TwelveMonths=100),NetTangibleAssets=NS(TwelveMonths=i+1)),CashFlowStatement=NS(OperatingCashFlow=NS(TwelveMonths=cf*100),CapExReported=NS(TwelveMonths=30 if good else 10)),IncomeStatement=NS(ResearchAndDevelopment=NS(TwelveMonths=40 if good else 10),SellingGeneralAndAdministration=NS(TwelveMonths=20 if good else 10))))
        self_obj=NS(Time=datetime(2016,4,1),quarters=14,tech_ROA={'T'+str(i):deque([.02]*11 if i==0 else [.1,.5]*5+[.1],maxlen=12) for i in range(4)})
        selected=ns['_source_select'](self_obj,[stock(i) for i in range(8)])
        self.assertEqual(self_obj._eligible,['T0','T1'])
        self.assertEqual(selected,['T0'])
        self.assertEqual(self_obj._variance_ready,4)

    def test_no_future_saved_state_and_fixed_context(self):
        for case in CASES:
            source=build_source(case);ast.parse(source)
            self.assertNotIn('pickle',source.split('from collections import deque',1)[1])
            self.assertNotIn('object_store',source.lower())
            self.assertIn('self.set_start_date(2013, 1, 1)',source)
            self.assertIn('self.time.year < 2016',source)
            self.assertIn('ConstantSlippageModel(0.0005)',source)
            self.assertIn('self.market_order(symbol, quantity)',source)
            self.assertLess(len(source),32000)
        self.assertIn('g_score >= 5',build_source('gscore'))

    def test_fragment_identity_completeness_and_checksum(self):
        raw=json.dumps({'study':'gscore-spy-v1','case':'probe','kind':'probe'},separators=(',',':'))
        line='GSC|probe|0|0|1|'+hashlib.sha256(raw.encode()).hexdigest()[:12]+'|'+raw
        self.assertEqual(decode_fragments([line],'probe')[0]['kind'],'probe')
        for bad in [line+'x',line.replace('|0|1|','|0|2|')]:
            with self.assertRaises(ValueError):decode_fragments([bad],'probe')
        with self.assertRaises(ValueError):decode_fragments([line],'gscore')
