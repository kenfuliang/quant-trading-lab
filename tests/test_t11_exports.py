"""Invented chart observations, not trading simulations or actual source data."""
from copy import deepcopy
from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from research.studies.t11_reproduction.exports import inspect_export
from research.studies.t11_reproduction.reference import legacy_metrics


class ExportReviewTests(unittest.TestCase):
    def fixture(self):
        def point(day, hour, nav):
            ts=int(datetime.fromisoformat(day).replace(hour=hour,tzinfo=ZoneInfo('America/New_York')).timestamp())
            return [ts,nav,nav,nav,nav]
        # Weekend midnight is the observation for Friday's close. Jan2midnight
        # is not Jan2close, and a10:00 point must not become a daily return.
        points=[point('2020-01-02',0,10000),point('2020-01-02',10,9800),
                point('2020-01-03',0,9000),point('2020-01-04',0,9500),
                point('2025-12-31',16,12000)]
        sessions=['2020-01-02','2020-01-03','2025-12-31']
        rows=[{'session':d,'nav_usd':v} for d,v in zip(sessions,[9000,9500,12000])]
        d={'state':{'Name':'fixture','Hostname':'BACKTESTING-com-test','Status':'Completed','RuntimeError':''},
           'algorithmConfiguration':{'startDate':'2020-01-01T00:00:00Z','endDate':'2025-12-31T23:59:59Z'},
           'statistics':{'Start Equity':'10000','End Equity':'12000','Total Orders':'0'},
           'charts':{'Strategy Equity':{'series':{'Equity':{'seriesType':2,'unit':'$','values':points}}}},'orders':{}}
        return d,dict(name='fixture',backtest_id='test',sessions=sessions,reference=legacy_metrics(rows))

    def test_midnight_mapping_and_terminal(self):
        d,args=self.fixture();a,rows=inspect_export(d,**args)
        self.assertTrue(a['legacy_aggregate_comparison']['aggregate_match'])
        self.assertEqual([r['nav_usd'] for r in rows],[9000,9500,12000])
        self.assertFalse(a['original_daily_parity'])
        self.assertFalse(a['cash_position_ledger_reconciled'])

    def test_duplicate_missing_nonfinite_ohlc_rejected(self):
        for change in ['duplicate','missing','nan','bad_ohlc','wrong_identity','wrong_dates']:
            d,args=self.fixture();p=d['charts']['Strategy Equity']['series']['Equity']['values']
            if change=='duplicate':p.insert(1,p[0])
            if change=='missing':p.pop(2)
            if change=='nan':p[2][-1]=float('nan')
            if change=='bad_ohlc':p[2][2]=1
            if change=='wrong_identity':d['state']['Hostname']='other'
            if change=='wrong_dates':d['algorithmConfiguration']['startDate']='2019-01-01T00:00:00Z'
            with self.subTest(change=change),self.assertRaises(ValueError):inspect_export(d,**args)

    def test_mismatch_is_preserved_without_promotion(self):
        d,args=self.fixture();args['reference']['cagr']+=.1
        audit,_=inspect_export(d,**args)
        self.assertEqual(audit['status'],'mismatch_preserved')

    def test_invalid_calendar_and_terminal(self):
        d,args=self.fixture()
        for session_list in [args['sessions'][::-1],args['sessions']+args['sessions'][-1:]]:
            with self.assertRaises(ValueError):inspect_export(d,**(args|{'sessions':session_list}))
        d['statistics']['End Equity']='13000'
        with self.assertRaises(ValueError):inspect_export(d,**args)

    def test_order_identity_counts_and_fill_time(self):
        d,args=self.fixture()
        order={'id':1,'createdTime':'2020-01-02T21:00:00Z','lastFillTime':'2020-01-03T21:00:00Z',
               'quantity':1,'price':100,'status':3,'type':4,'symbol':{'value':'SPY'}}
        d['orders']={'1':order};d['statistics']['Total Orders']='1'
        a,_=inspect_export(d,**args);self.assertEqual(a['status_code_counts'],{'3':1})
        for update in [{'id':2},{'lastFillTime':'2020-01-01T21:00:00Z'},{'quantity':float('nan')}]:
            bad=deepcopy(d);bad['orders']['1'].update(update)
            with self.assertRaises(ValueError):inspect_export(bad,**args)


if __name__=='__main__':unittest.main()
