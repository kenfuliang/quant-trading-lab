from decimal import Decimal
import unittest

import numpy as np
import pandas as pd

from research.multi_asset_plan import CASES, REQUIRED_GATES, require_ready
from research.multi_asset import (SYMBOLS, DividendReceivables,
                                 forward_total_return, monthly_decisions, plan_rebalance)


class MonthlySignalTests(unittest.TestCase):
    def test_forward_index_distribution_split_and_causal_prefix(self):
        index = pd.bdate_range('2020-01-01', periods=5)
        closes = pd.Series([50, 50, 50, 25, 25], index=index)
        payouts = pd.Series([0, 2, 0, 0, 0], index=index)
        splits = pd.Series([1, 1, 1, 2, 1], index=index)
        actual = forward_total_return(closes, payouts, splits)
        self.assertEqual(actual.tolist(), [100, 104, 104, 104, 104])
        changed = closes.copy()
        changed.iloc[-1] *= 3
        pd.testing.assert_series_equal(actual.iloc[:-1], forward_total_return(changed, payouts, splits).iloc[:-1])
        with self.assertRaises(ValueError):
            forward_total_return(closes, payouts.iloc[1:], splits)
        payouts.iloc[0] = 1
        with self.assertRaises(ValueError):
            forward_total_return(closes, payouts, splits)

    def test_concurrent_split_and_ex_date_preserve_economic_wealth(self):
        dates = pd.bdate_range('2020-01-01', periods=2)
        actual = forward_total_return(pd.Series([50, 23], index=dates),
                                      pd.Series([0, 2], index=dates),
                                      pd.Series([1, 2], index=dates))
        self.assertEqual(actual.tolist(), [100, 100])
        # Four old shares become eight new shares: 8*23 mark + 8*2 receivable.
        # This is an independent economic identity, not native split-handler proof.
        self.assertEqual(4*50, 8*23+8*2)

    def fixture(self):
        calendar = pd.bdate_range('2019-01-01', '2020-07-15')
        price = np.linspace(100, 150, len(calendar))
        return pd.DataFrame({s: price for s in SYMBOLS}, index=calendar), calendar

    def test_warmup_ties_and_completed_month_only(self):
        tri, calendar = self.fixture()
        records = monthly_decisions(tri, calendar)
        self.assertTrue(all(sum(r['trend_equal'].values()) == 0 for r in records[:9]))
        self.assertTrue(all(sum(r['relative_strength'].values()) == 0 for r in records[:10]))
        self.assertEqual(records[10]['relative_strength'], dict(GLD=1., IEF=0., SPY=0.))
        self.assertEqual(records[-1]['observed_close'], '2020-06-30')
        self.assertEqual(records[-1]['execution_open'], '2020-07-01')
        self.assertEqual(records[9]['trend_equal'], {s: 1/3 for s in SYMBOLS})
        self.assertTrue(all(pd.Timestamp(r['observed_close']) < pd.Timestamp(r['execution_open']) for r in records))

    def test_nonpositive_strength_stays_cash(self):
        tri, calendar = self.fixture()
        tri[:] = 100
        self.assertEqual(sum(monthly_decisions(tri, calendar)[-1]['relative_strength'].values()), 0)
        self.assertEqual(sum(monthly_decisions(tri, calendar)[-1]['trend_equal'].values()), 0)
        tri.iloc[:, :] = np.linspace(100, 50, len(calendar))[:, None]
        self.assertEqual(sum(monthly_decisions(tri, calendar)[-1]['relative_strength'].values()), 0)

    def test_future_perturbation_and_truncation_preserve_decisions(self):
        tri, calendar = self.fixture()
        reference = monthly_decisions(tri, calendar)
        cutoff = pd.Timestamp('2020-03-16')
        changed = tri.copy()
        changed.loc[cutoff:, 'SPY'] *= 3
        eligible = lambda rows: [r for r in rows if pd.Timestamp(r['execution_open']) <= cutoff]
        self.assertEqual(eligible(reference), eligible(monthly_decisions(changed, calendar)))
        past = tri.loc[:cutoff]
        self.assertEqual(eligible(reference), monthly_decisions(past, past.index))

    def test_missing_bad_or_misaligned_mark_stops(self):
        tri, calendar = self.fixture()
        changed = tri.copy()
        changed.iloc[100, 0] = np.nan
        for data, dates in ((changed, calendar), (tri.iloc[1:], calendar),
                            (tri.iloc[::-1], calendar[::-1]), (tri.drop(columns=['GLD']), calendar)):
            with self.assertRaises(ValueError):
                monthly_decisions(data, dates)


class AllocationTests(unittest.TestCase):
    def test_ten_case_design_cannot_bypass_readiness_with_unknown_or_truthy_values(self):
        self.assertEqual(len(CASES), 10)
        self.assertEqual(len({c['id'] for c in CASES}), 10)
        gates = {name: True for name in REQUIRED_GATES}
        self.assertFalse(require_ready({'remaining_gates': gates})['execution_started'])
        for value in (False, None, 'true', 1):
            with self.assertRaisesRegex(ValueError, 'launch blocked'):
                require_ready({'remaining_gates': gates | {'intended_use_rights': value}})
        with self.assertRaises(ValueError):
            require_ready({'remaining_gates': {}})

    def test_rotation_cash_conservation_and_deterministic_order(self):
        marks = dict(SPY=100, IEF=50, GLD=25)
        orders = plan_rebalance(72, dict(SPY=3, IEF=6, GLD=13), marks,
                                dict(SPY=0, IEF=0, GLD=1), cost_bps=0)
        self.assertEqual([(o.symbol, o.delta) for o in orders], [('IEF', -6), ('SPY', -3), ('GLD', 26)])
        cash = Decimal(72)
        positions = dict(SPY=3, IEF=6, GLD=13)
        for order in orders:
            cash -= order.delta * order.expected_fill + order.commission
            positions[order.symbol] += order.delta
            self.assertGreaterEqual(cash, 0)
        self.assertEqual(cash, 19)
        self.assertEqual(positions, dict(SPY=0, IEF=0, GLD=39))
        self.assertEqual(cash + sum(Decimal(marks[s])*positions[s] for s in SYMBOLS), 994)

    def test_fees_prevent_overspending_even_with_full_target(self):
        orders = plan_rebalance(300, {s: 0 for s in SYMBOLS},
                                {s: 100 for s in SYMBOLS}, dict(SPY=1, IEF=0, GLD=0),
                                reserve=1, cost_bps=0)
        self.assertEqual([(o.symbol, o.delta) for o in orders], [('SPY', 2)])
        orders = plan_rebalance(301, {s: 0 for s in SYMBOLS}, {s: 100 for s in SYMBOLS},
                                dict(SPY=1, IEF=0, GLD=0), reserve=1, cost_bps=0)
        self.assertEqual(orders[0].delta, 3)

    def test_invalid_missing_mark_leverage_short_and_nan_rejected(self):
        kwargs = dict(cash=1000, positions={s: 0 for s in SYMBOLS},
                      marks={s: 100 for s in SYMBOLS}, weights={s: 1/3 for s in SYMBOLS})
        for delta in (dict(cash=-1), dict(marks=dict(SPY=100, IEF=100)),
                      dict(weights=dict(SPY=1, IEF=1, GLD=0)),
                      dict(positions=dict(SPY=-1, IEF=0, GLD=0)), dict(cash=float('nan'))):
            with self.assertRaises(ValueError):
                plan_rebalance(**(kwargs | delta))

    def test_receivable_not_cash_and_pay_once_after_date(self):
        book = DividendReceivables()
        book.accrue('IEF-1', 'IEF', '2020-01-03', '2020-01-06', 2, 4)
        book.accrue('IEF-1', 'IEF', '2020-01-03', '2020-01-06', 2, 4)
        self.assertEqual(book.outstanding, 8)
        self.assertEqual(book.due('2020-01-03'), {})
        self.assertEqual(book.due('2020-01-06'), {'IEF-1': Decimal(8)})
        orders = plan_rebalance(0, {s: 0 for s in SYMBOLS}, {s: 100 for s in SYMBOLS}, dict(SPY=1, IEF=0, GLD=0))
        self.assertEqual(orders, [])  # 8 receivable never entered spendable cash
        for amount, day in ((8, '2020-01-03'), (9, '2020-01-06')):
            with self.assertRaises(ValueError):
                book.confirm_paid('IEF-1', amount, day)
        with self.assertRaises(ValueError):
            book.confirm_paid('IEF-1', 8, pd.NaT)
        book.confirm_paid('IEF-1', 8, '2020-01-06')
        self.assertEqual(book.outstanding, 0)
        with self.assertRaises(ValueError):
            book.confirm_paid('IEF-1', 8, '2020-01-06')
        with self.assertRaises(ValueError):
            book.accrue('IEF-1', 'IEF', '2020-01-03', '2020-01-06', 3, 4)


if __name__ == '__main__':
    unittest.main()
