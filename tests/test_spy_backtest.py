import unittest

import pandas as pd

from research.spy_backtest import audit_run, run_engine


def fixture():
    dates = pd.bdate_range("2020-01-01", periods=9).strftime("%Y-%m-%d")
    values = [10, 11, 12, 13, 14, 5, 6, 7, 8]
    return pd.DataFrame({"open": values, "high": [v + 1 for v in values],
                         "low": [v - 1 for v in values], "close": values,
                         "volume": [1_000_000] * len(values)}, index=dates)


class BacktestBehaviorTests(unittest.TestCase):
    def test_ex_date_buy_is_not_entitled_but_prior_holder_is(self):
        data = fixture()
        dividends = {"2020-01-06": .25, "2020-01-07": .50}
        curve, fills, credits, _ = run_engine(data, dividends, "buy_hold", start="2020-01-06", end="2020-01-13", fast=2, slow=3)
        self.assertEqual(list(credits.date), ["2020-01-07"])
        self.assertEqual(len(fills), 1)
        _, audit = audit_run(data, dividends, "buy_hold", curve, fills, credits, fast=2, slow=3)
        self.assertTrue(audit["passed"])

    def test_close_signal_cannot_fill_before_next_open(self):
        data = fixture()
        curve, fills, credits, _ = run_engine(data, {}, "trend", start="2020-01-06", end="2020-01-13", fast=2, slow=3)
        # The sharp decline is only known at Jan 8 close, so exit is Jan 9 open.
        sells = fills.loc[fills.side.astype(str) == "SELL"]
        self.assertEqual(str(pd.Timestamp(sells.iloc[0].ts_last).date()), "2020-01-09")
        _, audit = audit_run(data, {}, "trend", curve, fills, credits, fast=2, slow=3)
        self.assertTrue(audit["passed"])

    def test_future_data_does_not_change_prior_trades_or_equity(self):
        data = fixture()
        changed = data.copy()
        changed.loc[changed.index >= "2020-01-10", ["open", "high", "low", "close"]] *= 4
        runs = [run_engine(d, {}, "trend", start="2020-01-06", end="2020-01-13", fast=2, slow=3) for d in (data, changed)]
        pd.testing.assert_frame_equal(runs[0][0].loc[:"2020-01-09"], runs[1][0].loc[:"2020-01-09"])
        for curve, fills, credits, _ in runs:
            self.assertFalse(curve.empty)
            self.assertTrue((curve.cash >= 0).all())


if __name__ == "__main__":
    unittest.main()
