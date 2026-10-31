"""Offline tests of QC summary metrics and frozen source identity; no cloud runs."""
import ast
import math
from pathlib import Path
import unittest
import pandas as pd
from research.quantconnect.sector_metrics import summarize_path
from reporting.temporal import analyze_temporal

class SectorSummaryTests(unittest.TestCase):
    def test_drawdown_underwater_and_sharpe_against_existing_temporal_contract(self):
        values = [100., 110., 88., 90., 110., 108., 99.]
        dates = pd.bdate_range('2020-01-01', periods=len(values))
        rows = [(str(d.date()), v) for d,v in zip(dates[1:], values[1:])]
        got = summarize_path(rows, 100, str(dates[0].date()))
        _, table = analyze_temporal(pd.Series(values,index=dates), initial_capital=100.)
        returns = table.daily_return.iloc[1:]
        self.assertAlmostEqual(got['dd'], table.drawdown.min())
        self.assertAlmostEqual(got['sharpe'], returns.mean()/returns.std(ddof=1)*math.sqrt(252))
        self.assertEqual(got['uw'], int((table.drawdown.iloc[1:]<0).sum()))
        self.assertEqual(got['longest_uw'], 2)
        self.assertTrue(got['censored'])
        self.assertAlmostEqual(got['annual_calmar'], got['ret']/abs(got['dd']))

    def test_cash_is_undefined_ratio_not_infinite_or_zero_sharpe(self):
        got = summarize_path([('2020-01-02',100),('2020-01-03',100)],100,'2020-01-01')
        self.assertIsNone(got['sharpe']);self.assertIsNone(got['calmar'])
        self.assertEqual(got['uw'],0);self.assertFalse(got['censored'])

    def test_annual_reset_can_hide_underwater_carried_from_previous_year(self):
        full = summarize_path([('2019-12-31',120),('2020-01-02',100),('2020-12-31',110)],100,'2019-12-30')
        annual = summarize_path([('2020-12-31',110)],100,'2020-01-02')
        self.assertTrue(full['censored']);self.assertFalse(annual['censored'])
        self.assertLess(full['dd'],annual['dd'])

    def test_reject_invalid_or_duplicate_nav(self):
        for rows in [[('2020-01-02',0)],[('2020-01-02',float('nan'))],[('2020-01-02',100),('2020-01-02',100)]]:
            with self.assertRaises(ValueError):summarize_path(rows,100,'2020-01-01')

    def test_embedded_metrics_and_gate_are_exact_copies(self):
        port=ast.parse(Path('research/quantconnect/sector_comparison.py').read_text())
        prior=ast.parse(Path('research/quantconnect/spy_comparison.py').read_text())
        helper=ast.parse(Path('research/quantconnect/sector_metrics.py').read_text())
        find=lambda tree,name: next(n for n in tree.body if getattr(n,'name',None)==name)
        self.assertEqual(ast.dump(find(port,'GateCore')),ast.dump(find(prior,'GateCore')))
        self.assertEqual(ast.dump(find(port,'summarize_path')),ast.dump(find(helper,'summarize_path')))


class SectorReportIntegrityTests(unittest.TestCase):
    def fixture(self):
        import copy
        previous=300000.;anchor='2016-12-30';all_rows=[];summaries=[];peak=previous
        for y in range(2017,2026):
            first='2017-01-03' if y==2017 else f'{y}-01-03'
            rows=[(first,previous*.95),(f'{y}-12-31',previous*1.03)]
            r=summarize_path(rows,previous,anchor);uw=0
            for d,v in rows:
                peak=max(peak,v);uw+=int(v<peak)
            r.update(study='sector-v1',year=str(y),global_uw=uw,global_uw_fraction=uw/len(rows))
            summaries.append(r);all_rows.extend(rows);previous=rows[-1][1];anchor=rows[-1][0]
        full=summarize_path(all_rows,300000.,'2016-12-30')
        full.update(study='sector-v1',year='ALL',rejects=0,min_cash=5000,max_gross=.98,
                    first='2017-01-03',last='2025-12-31',calendar_hash='synthetic-shared-calendar')
        summaries.append(full)
        records={m:copy.deepcopy(summaries) for m in ['hold','equal','momentum','gate']}
        for m,rows in records.items():
            for r in rows:r['mode']=m
        return records

    def test_complete_synthetic_summary_passes(self):
        from scripts.build_sector_comparison import validate
        annual,overall=validate(self.fixture())
        self.assertEqual(len(annual),36);self.assertEqual(len(overall),4)

    def test_missing_year_and_calendar_mismatch_fail(self):
        from scripts.build_sector_comparison import validate
        r=self.fixture();r['hold'].pop(0)
        with self.assertRaises(ValueError):validate(r)
        r=self.fixture();r['gate'][-1]['calendar_hash']='different'
        with self.assertRaises(ValueError):validate(r)

    def test_corrupted_returns_and_underwater_counts_fail(self):
        from scripts.build_sector_comparison import validate
        r=self.fixture();r['equal'][0]['ret']+=.01
        with self.assertRaises(ValueError):validate(r)
        r=self.fixture();r['gate'][0]['global_uw']+=1
        with self.assertRaises(ValueError):validate(r)

    def test_execution_rejection_excludes_path(self):
        from scripts.build_sector_comparison import validate
        r=self.fixture();r['momentum'][-1]['rejects']=1
        with self.assertRaises(ValueError):validate(r)

if __name__=='__main__':unittest.main()
