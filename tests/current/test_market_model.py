import unittest
from dataclasses import replace

import numpy as np
import pandas as pd

from research.evaluation.market_model import (
    Decision,
    Dividend,
    MarketConfig,
    MarketDataError,
    Split,
    execution_price,
    history_view,
    sma_trend_targets,
    validate,
)
from research.evaluation.parity_fixture import synthetic_fixture


class MarketModelTests(unittest.TestCase):
    def test_fixture_is_valid_and_deterministic(self):
        a, b = synthetic_fixture(), synthetic_fixture()
        validate(a)
        self.assertEqual(len(a.sessions), 250)
        pd.testing.assert_frame_equal(a.bars["BBB"], b.bars["BBB"])
        self.assertEqual([s.ratio for s in a.splits], [2])
        self.assertEqual(len(a.dividends), 6)

    def test_fixture_split_and_dividend_shape(self):
        data = synthetic_fixture()
        split = data.splits[0]
        idx = data.sessions.index(split.effective_date)
        self.assertEqual(idx, 120)
        prev_close = data.bars["BBB"]["close"].iloc[idx - 1]
        self.assertEqual(round(prev_close * 100) % 2, 0)
        self.assertLess(data.bars["BBB"]["open"].iloc[idx], prev_close * 0.7)
        for d in data.dividends:
            self.assertEqual(data.sessions.index(d.pay_date) - data.sessions.index(d.ex_date), 5)
        self.assertEqual(sorted({d.instrument for d in data.dividends}), ["AAA", "CCC"])
        self.assertNotEqual(synthetic_fixture(8).bars["AAA"].iloc[5, 0], data.bars["AAA"].iloc[5, 0])

    def test_fixture_split_options(self):
        default = synthetic_fixture()
        explicit = synthetic_fixture(split_ratio=2, divisible_split_close=True)
        for name in default.bars:
            pd.testing.assert_frame_equal(default.bars[name], explicit.bars[name])
        data = synthetic_fixture(split_ratio=3, divisible_split_close=False)
        validate(data)
        idx = data.sessions.index(data.splits[0].effective_date)
        prev_close = data.bars["BBB"]["close"].iloc[idx - 1]
        self.assertEqual(data.splits[0].ratio, 3)
        self.assertNotEqual(round(prev_close * 100) % 3, 0)
        self.assertEqual(data.bars["BBB"]["open"].iloc[idx], round(prev_close / 3, 2))

    def test_rejects_missing_session(self):
        data = synthetic_fixture()
        bars = dict(data.bars, AAA=data.bars["AAA"].drop(data.sessions[10]))
        with self.assertRaises(MarketDataError):
            validate(replace(data, bars=bars))

    def test_rejects_split_between_ex_and_pay(self):
        data = synthetic_fixture()
        bad = Dividend("BBB", data.sessions[118], data.sessions[123], 0.1)
        with self.assertRaises(MarketDataError):
            validate(replace(data, dividends=data.dividends + (bad,)))

    def test_rejects_split_on_ex_or_pay_boundary(self):
        data = synthetic_fixture()
        for ex, pay in ((120, 125), (115, 120)):
            bad = Dividend("BBB", data.sessions[ex], data.sessions[pay], 0.1)
            with self.assertRaises(MarketDataError):
                validate(replace(data, dividends=data.dividends + (bad,)))

    def test_rejects_non_positive_and_inconsistent_ohlc(self):
        data = synthetic_fixture()
        for col, value in (("close", 0.0), ("high", 0.01)):
            frame = data.bars["AAA"].copy()
            frame.iloc[5, frame.columns.get_loc(col)] = value
            with self.assertRaises(MarketDataError):
                validate(replace(data, bars=dict(data.bars, AAA=frame)))

    def test_rejects_prices_off_the_cent_grid(self):
        data = synthetic_fixture()
        for col in ("open", "high", "low", "close"):
            frame = data.bars["AAA"].copy()
            frame.iloc[5, frame.columns.get_loc(col)] += 0.003
            with self.subTest(col=col), self.assertRaises(MarketDataError) as caught:
                validate(replace(data, bars=dict(data.bars, AAA=frame)))
            self.assertIn("cent", str(caught.exception))

    def test_rejects_unsorted_or_duplicate_sessions(self):
        data = synthetic_fixture()
        swapped = (data.sessions[1], data.sessions[0]) + data.sessions[2:]
        with self.assertRaises(MarketDataError):
            validate(replace(data, sessions=swapped))
        dup = data.sessions[:5] + (data.sessions[4],) + data.sessions[6:]
        with self.assertRaises(MarketDataError):
            validate(replace(data, sessions=dup))

    def test_rejects_unknown_instrument_or_session_in_actions(self):
        data = synthetic_fixture()
        for kwargs in (
            {"dividends": (Dividend("ZZZ", data.sessions[3], data.sessions[8], 0.1),)},
            {"dividends": (Dividend("AAA", data.sessions[3], "2030-01-01", 0.1),)},
            {"splits": (Split("ZZZ", data.sessions[3], 2),)},
            {"splits": (Split("AAA", "2030-01-01", 2),)},
            {"splits": (Split("AAA", data.sessions[3], 1),)},
        ):
            with self.assertRaises(MarketDataError):
                validate(replace(data, **kwargs))

    def test_execution_price_rounds_to_cents(self):
        self.assertEqual(execution_price(100.0, "BUY", 5.0), 100.05)
        self.assertEqual(execution_price(100.0, "SELL", 5.0), 99.95)

    def test_market_config_defaults(self):
        cfg = MarketConfig()
        self.assertEqual((cfg.initial_cash, cfg.cost_bps, cfg.commission_usd), (100_000.0, 5.0, 1.0))

    def test_sma_trend_targets(self):
        data = synthetic_fixture()
        fn = sma_trend_targets(window=20, gross=0.95)
        early = data.sessions[18]
        bars = history_view(data, 18)
        d = fn(early, bars, {}, 100_000.0)
        self.assertIsInstance(d, Decision)
        self.assertEqual(set(d.targets), {"AAA", "BBB", "CCC"})
        self.assertTrue(all(v == 0 for v in d.targets.values()))
        t = data.sessions[60]
        bars = history_view(data, 60)
        d = fn(t, bars, {}, 100_000.0)
        up = [k for k in bars if bars[k]["close"].iloc[-1] > bars[k]["close"].iloc[-20:].mean()]
        for k in bars:
            close = bars[k]["close"].iloc[-1]
            expected = int(0.95 / len(up) * 100_000.0 / close) if k in up else 0
            self.assertEqual(d.targets[k], expected)
            self.assertAlmostEqual(d.signals[(k, "trend")], close / bars[k]["close"].iloc[-20:].mean() - 1)


def _reference_history_view(data, i):
    """Verbatim copy of the original per-session-copy construction; guards the optimised view."""
    effective = {}
    for split in data.splits:
        k = data.sessions.index(split.effective_date)
        if k <= i:
            effective.setdefault(split.instrument, []).append((k, split.ratio))
    view = {}
    for name, frame in data.bars.items():
        factor = np.ones(i + 1)
        for k, ratio in effective.get(name, ()):
            factor[:k] *= ratio
        view[name] = frame.iloc[: i + 1].assign(split_factor=factor)
    return view


class HistoryViewTests(unittest.TestCase):
    def test_history_view_matches_reference(self):
        for ratio in (2, 4):
            data = synthetic_fixture(split_ratio=ratio)
            for i in range(len(data.sessions)):
                got, want = history_view(data, i), _reference_history_view(data, i)
                self.assertEqual(list(got), list(want))
                for name in want:
                    pd.testing.assert_frame_equal(got[name], want[name], check_exact=True)

    def test_split_factor_around_the_bbb_split(self):
        data = synthetic_fixture()
        k = data.sessions.index(data.splits[0].effective_date)
        view = history_view(data, k + 5)
        self.assertEqual(set(view), set(data.bars))
        self.assertEqual(list(view["BBB"].index), list(data.sessions[: k + 6]))
        factor = view["BBB"]["split_factor"]
        self.assertTrue((factor.iloc[:k] == 2.0).all())
        self.assertTrue((factor.iloc[k:] == 1.0).all())
        self.assertTrue((view["AAA"]["split_factor"] == 1.0).all())
        pd.testing.assert_frame_equal(view["BBB"][list(data.bars["BBB"].columns)], data.bars["BBB"].iloc[: k + 6])

    def test_no_future_split_leaks_into_earlier_history(self):
        data = synthetic_fixture()
        k = data.sessions.index(data.splits[0].effective_date)
        view = history_view(data, k - 1)
        self.assertEqual(len(view["BBB"]), k)
        self.assertTrue((view["BBB"]["split_factor"] == 1.0).all())

    def test_view_does_not_alter_market_data(self):
        data = synthetic_fixture()
        history_view(data, 200)
        self.assertNotIn("split_factor", data.bars["BBB"].columns)

    def test_sma_on_bbb_is_not_distorted_by_the_split(self):
        data = synthetic_fixture()
        k = data.sessions.index(data.splits[0].effective_date)
        view = history_view(data, k + 2)
        d = sma_trend_targets(window=20)(data.sessions[k + 2], view, {}, 100_000.0)
        frame = view["BBB"]
        adjusted = frame["close"] / frame["split_factor"]
        expected = frame["close"].iloc[-1] / adjusted.iloc[-20:].mean() - 1
        self.assertAlmostEqual(d.signals[("BBB", "trend")], expected)
        self.assertLess(abs(d.signals[("BBB", "trend")]), 0.1)   # raw closes would give about -0.45


if __name__ == "__main__":
    unittest.main()
