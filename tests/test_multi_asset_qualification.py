from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import pandas as pd

from research.issuer_actions import ssga_spy, ishares_ief, validate
from research.native_multi_asset import DistributionBook, run_native
from research.us_etf_calendar import sessions, clocks
from research.multi_asset_cash_audit import reconcile
from research.multi_asset_comparison import score, load_bundle
from research import multi_asset_comparison
from unittest.mock import patch


class QualificationTests(unittest.TestCase):
    def test_missing_permission_bundle_blocks_without_simulation(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(multi_asset_comparison,'BUNDLE',Path(temporary)/'missing.json'), \
             patch.object(multi_asset_comparison,'run_native') as engine:
            with self.assertRaisesRegex(ValueError,'Qualified price-use'):
                load_bundle()
            engine.assert_not_called()

    def test_independent_account_audit_rejects_money_and_fill_corruption(self):
        index = pd.Index(['2020-01-02'],name='date')
        frames = {s:pd.DataFrame(dict(open=[100],close=[100]),index=index) for s in ('GLD','IEF','SPY')}
        targets = {'2020-01-02':dict(SPY=1,IEF=0,GLD=0)}
        curve = pd.DataFrame([dict(cash=98.55,receivable=0,position_value=900,equity_usd=998.55,SPY=9,IEF=0,GLD=0)],index=index)
        trades = pd.DataFrame([dict(date='2020-01-02',symbol='SPY',delta=9,fill_price='100.05',commission='1')])
        self.assertTrue(reconcile(frames,targets,[],curve,trades,[],capital=1000)['passed'])
        wrong = curve.copy()
        wrong.loc[index[0],'cash'] += .01
        with self.assertRaises(AssertionError):
            reconcile(frames,targets,[],wrong,trades,[],capital=1000)
        with self.assertRaises(AssertionError):
            reconcile(frames,targets,[],curve,trades.iloc[:0],[],capital=1000)

    def test_native_summary_annual_scores_anchor_prior_year_end(self):
        curve = pd.DataFrame({'equity_usd':[300000.,330000.,297000.,356400.]},
                             index=['2020-01-02','2020-12-31','2021-01-04','2021-12-31'])
        result = score(curve,'fixture')
        self.assertEqual([r['period'] for r in result],['Overall','2020','2021'])
        self.assertAlmostEqual(result[1]['return_pct'],10)
        self.assertAlmostEqual(result[2]['return_pct'],8)
        self.assertAlmostEqual(result[2]['drawdown_pct'],-10)

    def test_issuer_xlsx_cell_positions_and_identity(self):
        strings = ['SPY','78462F103','12/17/2021','01/31/2022','1.636431']
        root = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        shared = f'<sst xmlns="{root}">' + ''.join('<si><t>'+s+'</t></si>' for s in strings) + '</sst>'
        cells = [('B1',0),('C1',1),('D1',2),('F1',3),('G1',4)]
        sheet = f'<worksheet xmlns="{root}"><sheetData><row>'+''.join(f'<c r="{c}" t="s"><v>{i}</v></c>' for c,i in cells)+'</row></sheetData></worksheet>'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'issuer.xlsx'
            with zipfile.ZipFile(path, 'w') as book:
                book.writestr('xl/sharedStrings.xml',shared)
                book.writestr('xl/worksheets/sheet1.xml',sheet)
            rows = ssga_spy(path)
            self.assertEqual(rows, [dict(symbol='SPY', ex_date='2021-12-17', pay_date='2022-01-31', amount='1.636431', id='SPY-2021-12-17')])

    def test_issuer_html_embedded_table_and_missing_rows(self):
        data = {'distributionTableData':[
            {'name':'exDate','value':[20200103]},
            {'name':'payableDate','value':[20200106]},
            {'name':'totalDistribution','value':['0.123456']}]}
        import html
        content = '<walrus-render-on-client componentprops="'+html.escape(json.dumps(data),quote=True)+'"></walrus-render-on-client>'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'issuer.html'
            path.write_text(content)
            self.assertEqual(ishares_ief(path)[0]['amount'],'0.123456')
            path.write_text('<html></html>')
            with self.assertRaises(ValueError):
                ishares_ief(path)

    def test_invalid_duplicate_and_early_payment_actions_stop(self):
        action = dict(symbol='SPY', ex_date='2020-01-03', pay_date='2020-01-06', amount='1')
        for rows in ([action.copy(),action.copy()], [action | dict(pay_date='2020-01-02')], [action | dict(amount='NaN')]):
            with self.assertRaises(ValueError):
                validate(rows)

    def test_calendar_exceptional_closures_and_new_year_saturday(self):
        for day in ('2004-06-11','2007-01-02','2012-10-29','2012-10-30','2018-12-05','2025-01-09','2022-06-20'):
            self.assertEqual(len(sessions(day,day)),0)
        for day in ('2004-12-31','2010-12-31','2021-12-31','2021-06-18'):
            self.assertEqual(len(sessions(day,day)),1)
        self.assertEqual(clocks('2024-11-29')[1].hour,18)
        self.assertEqual(clocks('2025-07-03')[1].hour,17)
        with self.assertRaises(ValueError):
            sessions('2003-12-31','2004-01-02')

    def test_payment_rounding_wealth_and_duplicate_processing(self):
        a = dict(id='a',symbol='SPY',ex_date='2020-01-03',pay_date='2020-01-06',amount='0.123456')
        book = DistributionBook([a])
        credits = []
        book.day('2020-01-03',dict(SPY=9,IEF=0,GLD=0),credits.append)
        self.assertEqual(book.outstanding,Decimal('1.111104'))
        self.assertEqual(credits,[])
        book.day('2020-01-06',dict(SPY=0,IEF=0,GLD=0),credits.append)
        self.assertEqual(credits,[Decimal('1.11')])
        self.assertEqual(book.outstanding,0)
        self.assertEqual(book.events[-1]['rounding_pnl'],'-0.001104')
        book.day('2020-01-06',dict(SPY=0,IEF=0,GLD=0),credits.append)
        self.assertEqual(len(credits),1)
        with self.assertRaises(ValueError):
            book.day('2020-01-03',dict(SPY=9,IEF=0,GLD=0),credits.append)

    def test_same_day_ex_payment_and_terminal_entitlement(self):
        actions = [dict(id='same',symbol='IEF',ex_date='2020-01-03',pay_date='2020-01-03',amount='2'),
                   dict(id='later',symbol='SPY',ex_date='2020-01-03',pay_date='2020-01-31',amount='1')]
        book = DistributionBook(actions)
        credits=[]
        book.day('2020-01-03',dict(SPY=3,IEF=4,GLD=0),credits.append)
        self.assertEqual(credits,[Decimal(8)])
        self.assertEqual(book.outstanding,3)

    def test_unhandled_split_rejected_before_engine(self):
        with self.assertRaisesRegex(ValueError,'split'):
            run_native({}, {}, [], splits=[dict(symbol='IEF',ratio=2)])


if __name__ == '__main__':
    unittest.main()
