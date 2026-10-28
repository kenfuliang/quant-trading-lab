from dataclasses import replace
import unittest

import numpy as np
import pandas as pd

from research.evaluation.leveraged_spy import FinancingModel, simulate, score_rows, target_shares
from research.evaluation.leverage_audit import reconcile


def data(prices, dates=None, signals=None):
    if dates is None: dates=pd.date_range('2020-01-02',periods=len(prices)).strftime('%Y-%m-%d')
    return pd.DataFrame({'open':[p[0] for p in prices],'low':[p[1] for p in prices],
                         'close':[p[2] for p in prices],'want_long':signals if signals is not None else [True]*len(prices)},index=dates)


class FinancingTests(unittest.TestCase):
    model=FinancingModel(capital=1000,cost_bps=0,commission=0)

    def test_weekend_interest_and_prior_holding_dividends(self):
        frame=data([(100,100,100),(100,100,100)],['2020-01-03','2020-01-06'])
        curve,trades=simulate(frame,{'2020-01-06':.5},'buy_hold',1.5,self.model)
        self.assertEqual(curve.iloc[0].shares,14)
        self.assertAlmostEqual(curve.iloc[1].financing_usd,.2)
        self.assertAlmostEqual(curve.iloc[1].dividend_usd,7)
        self.assertAlmostEqual(curve.iloc[1].cash,-393.2)
        self.assertTrue(reconcile(frame,{'2020-01-06':.5},curve,trades,'buy_hold',1.5,self.model)['passed'])

    def test_no_dividend_for_ex_date_new_entry_and_no_interest_at_1x(self):
        frame=data([(100,100,100),(100,100,100)])
        curve,_=simulate(frame,{frame.index[0]:1},'buy_hold',1,self.model)
        self.assertEqual(curve.dividend_usd.sum(),0)
        self.assertEqual(curve.financing_usd.sum(),0)
        self.assertTrue((curve.cash>=0).all())

    def test_close_does_not_change_same_open_fill(self):
        first=data([(100,90,100),(100,90,100)])
        second=first.copy();second.iloc[0,second.columns.get_loc('close')]=200
        _,a=simulate(first,{},'trend',1.5,self.model)
        _,b=simulate(second,{},'trend',1.5,self.model)
        self.assertEqual(a.iloc[0].delta,b.iloc[0].delta)
        self.assertEqual(a.iloc[0].fill_price,b.iloc[0].fill_price)

    def test_signal_cash_exit_and_no_new_entry_when_false(self):
        frame=data([(100,100,100)]*3,signals=[False,True,False])
        curve,trades=simulate(frame,{},'trend',1.5,self.model)
        self.assertEqual(list(curve.shares),[0,14,0])
        self.assertEqual(len(trades),2)

    def test_gap_margin_breach_liquidates_before_rebalance_and_halts(self):
        frame=data([(100,100,100),(50,50,50),(100,100,100)])
        curve,trades=simulate(frame,{},'buy_hold',2,self.model)
        self.assertEqual(trades.iloc[-1].reason,'forced_open')
        self.assertEqual(curve.forced_liquidations.sum(),1)
        self.assertEqual(curve.iloc[-1].shares,0)
        self.assertTrue(curve.iloc[-1].halted)
        self.assertTrue(reconcile(frame,{},curve,trades,'buy_hold',2,self.model)['passed'])

    def test_low_price_margin_breach(self):
        frame=data([(100,50,100),(100,100,100)])
        curve,trades=simulate(frame,{},'buy_hold',2,self.model)
        self.assertEqual(trades.iloc[-1].reason,'forced_low')
        self.assertEqual(curve.iloc[-1].shares,0)

    def test_initial_margin_rejection(self):
        frame=data([(100,100,100)])
        curve,trades=simulate(frame,{},'buy_hold',2,replace(self.model,initial_margin=.9))
        self.assertTrue(trades.empty)
        self.assertEqual(curve.initial_margin_rejections.sum(),1)

    def test_insolvency_preserves_debt_and_scores_unranked(self):
        frame=data([(100,100,100),(1,1,1),(1,1,1)])
        curve,trades=simulate(frame,{},'buy_hold',2,self.model)
        self.assertLess(curve.iloc[-1].equity_usd,0)
        self.assertGreater(curve.iloc[-1].financing_usd,0)
        row=score_rows(curve,self.model,'test','buy_hold',2)[0]
        self.assertTrue(np.isnan(row['calmar']))
        self.assertTrue(np.isnan(row['sharpe']))
        self.assertEqual(row['status'],'INSOLVENT')
        self.assertTrue(reconcile(frame,{},curve,trades,'buy_hold',2,self.model)['passed'])

    def test_target_respects_post_cost_equity(self):
        model=replace(self.model,commission=1,cost_bps=5)
        n=target_shares(1000,0,100,2,model)
        from research.evaluation.leveraged_spy import fill_price
        equity=1000-n*(fill_price(100,True,model)-100)-1
        self.assertLessEqual(n*100,1.98*equity)
        equity_next=1000-(n+1)*(fill_price(100,True,model)-100)-1
        self.assertGreater((n+1)*100,1.98*equity_next)

    def test_invalid_config_and_prices_fail_closed(self):
        with self.assertRaises(ValueError): FinancingModel(annual_rate=-.1)
        with self.assertRaises(ValueError): simulate(data([(100,0,100)]),{},'trend',2,self.model)


class AllocationPolicyTests(unittest.TestCase):
    model=FinancingModel(capital=1000,cost_bps=0,commission=0,annual_rate=0)

    def test_factor_can_reduce_exposure_to_cash(self):
        frame=data([(100,100,100)]*3)
        frame['allocation_factor']=[1,.5,0]
        curve,trades=simulate(frame,{},'trend',2,self.model)
        self.assertEqual(list(curve.shares),[19,9,0])
        self.assertTrue(reconcile(frame,{},curve,trades,'trend',2,self.model)['passed'])

    def test_cppi_uses_prior_equity_and_can_fail_after_gap(self):
        frame=data([(100,100,100),(100,100,120),(1,1,1)])
        frame['cppi_floor_fraction']=.8;frame['cppi_multiplier']=3
        curve,trades=simulate(frame,{},'trend',2,self.model)
        self.assertEqual(curve.iloc[0].shares,5)
        self.assertEqual(curve.iloc[1].shares,5)
        self.assertLess(curve.iloc[-1].equity_usd,800)
        self.assertTrue(reconcile(frame,{},curve,trades,'trend',2,self.model)['passed'])

    def test_invalid_factor_is_rejected(self):
        frame=data([(100,100,100)]);frame['allocation_factor']=float('nan')
        with self.assertRaises(ValueError):simulate(frame,{},'trend',1,self.model)


class OvernightScheduleTests(unittest.TestCase):
    def test_close_entry_open_exit_and_weekend_financing(self):
        model=FinancingModel(capital=1000,cost_bps=0,commission=0)
        frame=data([(100,10,100),(110,10,100)],['2020-01-03','2020-01-06'])
        frame['execution_schedule']='overnight'
        curve,trades=simulate(frame,{'2020-01-06':1},'trend',1.5,model)
        self.assertEqual(trades.iloc[0].reason,'overnight_entry')
        self.assertEqual(trades.iloc[1].reason,'overnight_exit')
        self.assertEqual(trades.iloc[1].fill_price,110)
        self.assertAlmostEqual(curve.iloc[1].financing_usd,.2)
        self.assertAlmostEqual(curve.iloc[1].dividend_usd,14)
        self.assertAlmostEqual(curve.iloc[1].equity_usd,1153.8)
        self.assertEqual(curve.forced_liquidations.sum(),0)
        self.assertTrue(reconcile(frame,{'2020-01-06':1},curve,trades,'trend',1.5,model)['passed'])

    def test_open_gap_liquidates_before_scheduled_exit(self):
        model=FinancingModel(capital=1000,cost_bps=0,commission=0)
        frame=data([(100,100,100),(50,50,50)]);frame['execution_schedule']='overnight'
        curve,trades=simulate(frame,{},'trend',2,model)
        self.assertEqual(trades.iloc[-1].reason,'forced_open')
        self.assertTrue(curve.iloc[-1].halted)
        self.assertTrue(reconcile(frame,{},curve,trades,'trend',2,model)['passed'])
