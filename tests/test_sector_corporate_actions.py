"""Synthetic action-accounting and causal feature checks, no historical runs."""
from decimal import Decimal as D
import tempfile
from pathlib import Path
import unittest
import pandas as pd
from research.sector_corporate_actions import ActionLedger,total_return_indexes,normalize_splits

def cash(ex='2020-01-03',pay='2020-01-06',amount='1.25'):
    return dict(id='div',symbol='SPY',kind='cash',ex_date=ex,pay_date=pay,amount=amount)
def split(day='2020-01-06',ratio='2'):
    return dict(id='split',symbol='SPY',kind='split',ex_date=day,ratio=ratio)
def book(actions):return ActionLedger(actions,capital='1000',symbols=('SPY',))

class TestSectorCorporateActions(unittest.TestCase):
    def buy(self,b,day='2020-01-02',n=3,price='100'):
        b.before_open(day);b.fill('SPY',n,price);b.close(day,{'SPY':price})

    def test_entitlement_survives_ex_date_sale(self):
        b=book([cash()]);self.buy(b)
        b.before_open('2020-01-03');self.assertEqual(b.outstanding,D('3.75'));self.assertEqual(b.cash,D(699))
        b.fill('SPY',-3,'100');self.assertEqual(b.close('2020-01-03',{'SPY':100}),D('1001.75'))
        b.before_open('2020-01-06');self.assertEqual(b.cash,D(998))
        b.close('2020-01-06',{'SPY':100});self.assertEqual(b.cash,D('1001.75'));self.assertEqual(b.outstanding,0)

    def test_same_day_payment_not_spendable_at_open(self):
        b=book([cash(pay='2020-01-03',amount='100')]);self.buy(b,n=9)
        b.before_open('2020-01-03')
        with self.assertRaises(ValueError):b.fill('SPY',2,'100')
        self.assertEqual(b.cash,99);b.close('2020-01-03',{'SPY':100});self.assertEqual(b.cash,999)

    def test_ex_date_buy_not_eligible(self):
        b=book([cash()]);b.before_open('2020-01-03');b.fill('SPY',3,100)
        self.assertEqual(b.outstanding,0);b.close('2020-01-03',{'SPY':100})
        b.before_open('2020-01-06');b.close('2020-01-06',{'SPY':100});self.assertEqual(b.cash,699)

    def test_prior_entitlement_dollars_unchanged_by_split(self):
        b=book([cash(),split()]);self.buy(b)
        b.before_open('2020-01-03');b.close('2020-01-03',{'SPY':100})
        b.before_open('2020-01-06');self.assertEqual(b.shares['SPY'],6);self.assertEqual(b.outstanding,D('3.75'))
        self.assertEqual(b.close('2020-01-06',{'SPY':50}),D('1002.75'))

    def test_split_value_continuity_no_fill_or_fee(self):
        b=book([split()]);self.buy(b)
        b.before_open('2020-01-06');self.assertEqual(b.shares['SPY'],6)
        self.assertEqual(b.close('2020-01-06',{'SPY':50}),999);self.assertEqual(b.cash,699)
        self.assertEqual(len([e for e in b.events if e['kind']=='split']),1)

    def test_concurrent_split_and_cash_per_post_split_share(self):
        b=book([split(),cash(ex='2020-01-06',pay='2020-01-06')]);self.buy(b)
        b.before_open('2020-01-06');self.assertEqual(b.outstanding,D('7.50'))
        self.assertEqual(b.close('2020-01-06',{'SPY':50}),D('1006.50'))

    def test_half_even_rounding_and_idempotence(self):
        b=book([cash(ex='2020-01-03',pay='2020-01-03',amount='.005')]);self.buy(b,n=1)
        b.before_open('2020-01-03');b.before_open('2020-01-03');b.close('2020-01-03',{'SPY':100});b.close('2020-01-03',{'SPY':100})
        self.assertEqual(b.cash,899);self.assertEqual(len([e for e in b.events if e['kind']=='payment']),1)
        self.assertEqual(b.events[-1]['rounding_pnl'],'-0.005')

    def test_unpaid_terminal_receivable_in_nav_not_cash(self):
        b=book([cash(pay='2020-02-01')]);self.buy(b)
        b.before_open('2020-01-03');self.assertEqual(b.close('2020-01-03',{'SPY':100}),D('1002.75'));self.assertEqual(b.cash,699)

    def test_weekend_payment_available_next_open(self):
        b=book([cash(pay='2020-01-04')]);self.buy(b)
        b.before_open('2020-01-03');b.close('2020-01-03',{'SPY':100});b.before_open('2020-01-06');self.assertEqual(b.cash,D('702.75'))

    def test_invalid_split_atomic_and_held_in_kind_rejected(self):
        b=book([split(ratio='.5')]);self.buy(b)
        with self.assertRaisesRegex(ValueError,'Fractional'):b.before_open('2020-01-06')
        self.assertEqual(b.shares['SPY'],3);self.assertEqual(b.cash,699)
        a=dict(id='inkind',symbol='SPY',kind='in_kind',ex_date='2020-01-06',ratio='.1',child_symbol='XLRE')
        c=book([a]);self.buy(c)
        with self.assertRaisesRegex(ValueError,'Held in-kind'):c.before_open('2020-01-06')

    def test_duplicate_date_and_missing_marks_fail_closed(self):
        with self.assertRaises(ValueError):book([cash(),{**cash(),'id':'second'}])
        b=book([]);b.before_open('2020-01-02')
        with self.assertRaises(ValueError):b.close('2020-01-02',{})
        with self.assertRaises(ValueError):b.fill('SPY',0,100)

    def test_dividend_and_split_feature_no_double_counting(self):
        ix=pd.date_range('2020-01-02',periods=3);f={'SPY':pd.DataFrame({'close':[100,99,49.5]},index=ix)}
        result=total_return_indexes(f,[cash(pay='2020-01-03',amount='1'),split(day='2020-01-04')])['SPY']
        self.assertEqual(list(result),[100,100,100])

    def test_in_kind_uses_same_day_child_value_not_ratio_as_cash(self):
        ix=pd.date_range('2016-09-18',periods=2);frames={'SPY':pd.DataFrame({'close':[100,90]},index=ix),'XLRE':pd.DataFrame({'close':[50,50]},index=ix)}
        a=dict(id='inkind',symbol='SPY',kind='in_kind',ex_date='2016-09-19',ratio='.2',child_symbol='XLRE')
        self.assertEqual(list(total_return_indexes(frames,[a])['SPY']),[100,100])

    def test_future_action_and_future_price_do_not_change_prefix(self):
        ix=pd.date_range('2020-01-01',periods=4);f={'SPY':pd.DataFrame({'close':[100,101,102,103]},index=ix)}
        a=[cash(ex='2020-01-04',pay='2020-01-06')]
        full=total_return_indexes(f,a)['SPY'];prefix=total_return_indexes({'SPY':f['SPY'].iloc[:3]},a)['SPY']
        self.assertEqual(list(full.iloc[:3]),list(prefix))
        f['SPY'].iloc[-1,0]=999;self.assertEqual(list(total_return_indexes(f,a)['SPY'].iloc[:3]),list(prefix))

    def test_split_requires_external_issuer_review(self):
        pages=[{'corporate_actions':{'forward_splits':[dict(symbol='SPY',ex_date='2020-01-06',new_rate=2,old_rate=1)]}}]
        with self.assertRaises(ValueError):normalize_splits(pages,{})
        review={'SPY':dict(ex_date='2020-01-06',ratio='2',source_sha256='a'*64)}
        self.assertEqual(normalize_splits(pages,review)[0]['ratio'],'2')

class TestIssuerWorkbook(unittest.TestCase):
    def fixture(self, path, *, zero=False, duplicate=False, bad_header=False):
        import zipfile,xml.etree.ElementTree as ET
        from research.sector_corporate_actions import NS,SYMBOLS
        ns=NS['s'];sheet=ET.Element('{'+ns+'}worksheet');data=ET.SubElement(sheet,'{'+ns+'}sheetData');strings=[]
        def row(n,values):
            r=ET.SubElement(data,'{'+ns+'}row',r=str(n))
            for k,text in values.items():
                strings.append(text);c=ET.SubElement(r,'{'+ns+'}c',r=k+str(n),t='s');ET.SubElement(c,'{'+ns+'}v').text=str(len(strings)-1)
        row(1,{'B':'TICKER','C':'CUSIP','D':'EX-DATE','F':'PAYABLE DATE','G':'DIVIDEND ($)' if not bad_header else 'WRONG','H':'SHORT TERM CAPITAL GAIN ($)','I':'LONG TERM CAPITAL GAIN ($)'})
        for i,s in enumerate(SYMBOLS):
            row(i+2,{'B':s,'C':f'{i:09d}','D':'01/03/2020','F':'01/06/2020','G':'1','H':'.25','I':'.50'})
        if zero:row(30,{'B':'XLRE','C':f'{SYMBOLS.index("XLRE"):09d}','D':'02/03/2020','F':'02/06/2020','G':'0'})
        if duplicate:row(31,{'B':'SPY','C':f'{SYMBOLS.index("SPY"):09d}','D':'01/03/2020','F':'01/06/2020','G':'1'})
        shared=ET.Element('{'+ns+'}sst')
        for s in strings:ET.SubElement(ET.SubElement(shared,'{'+ns+'}si'),'{'+ns+'}t').text=s
        with zipfile.ZipFile(path,'w') as z:z.writestr('xl/sharedStrings.xml',ET.tostring(shared));z.writestr('xl/worksheets/sheet1.xml',ET.tostring(sheet))

    def test_components_and_zero_rows_preserved_explicitly(self):
        from research.sector_corporate_actions import workbook_actions
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'book.xlsx';self.fixture(p,zero=True);actions,ids,excluded=workbook_actions(p)
            self.assertEqual(len(actions),11);self.assertTrue(all(a['amount']=='1.75' for a in actions));self.assertEqual(len(excluded),1)
            self.assertEqual(excluded[0]['reason'],'issuer_explicit_zero_distribution')

    def test_duplicate_and_schema_refused(self):
        from research.sector_corporate_actions import workbook_actions
        with tempfile.TemporaryDirectory() as d:
            for opts in [{'duplicate':True},{'bad_header':True}]:
                p=Path(d)/'book.xlsx';self.fixture(p,**opts)
                with self.assertRaises(ValueError):workbook_actions(p)
