import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.policies.model_signals import (_fit_mixture, _fit_ridge, _posterior,
                                    build_model_signal)


def market(length=700):
    rng = np.random.default_rng(812)
    change = rng.normal(.0006, .012, length)
    close = 100 * np.exp(np.cumsum(change))
    opening = np.r_[100., close[:-1]]
    return pd.DataFrame({'open': opening, 'close': close,
                         'high': np.maximum(opening, close) + .1,
                         'low': np.minimum(opening, close) - .1},
                        index=pd.bdate_range('2004-01-02', periods=length))


class ModelSignalTests(unittest.TestCase):
    def test_prefix_and_future_labels_cannot_change_history(self):
        data = market()
        for strategy in (98, 99):
            with self.subTest(strategy=strategy):
                full = build_model_signal(data, strategy)
                short = build_model_signal(data.iloc[:503], strategy)
                pd.testing.assert_frame_equal(full.iloc[:503], short)
                changed = data.copy()
                changed.iloc[503:, :] *= 1.7
                # Change future open-to-close labels independently as well.
                changed.loc[changed.index[503:], 'open'] *= .99
                changed.loc[changed.index[503:], 'low'] = changed.iloc[503:][['open', 'close']].min(axis=1) - .2
                pd.testing.assert_frame_equal(full.iloc[:503], build_model_signal(changed, strategy).iloc[:503])

    def test_warmup_and_determinism(self):
        data = market()
        for strategy, warmup in ((98, 302), (99, 253)):
            with self.subTest(strategy=strategy):
                signal = build_model_signal(data, strategy)
                self.assertFalse(signal.want_long.iloc[:warmup].any())
                self.assertEqual(signal.want_long.dtype, bool)
                self.assertFalse(signal.want_long.isna().any())
                self.assertFalse(build_model_signal(data.iloc[:252], strategy).want_long.any())
                pd.testing.assert_frame_equal(signal, build_model_signal(data, strategy))

    def test_ridge_uses_realized_labels_and_excludes_current_feature(self):
        data = market(450)
        seen = []
        def record(x, y):
            seen.append((x.copy(), y.copy()))
            return _fit_ridge(x, y)
        with patch('research.policies.model_signals._fit_ridge', side_effect=record):
            build_model_signal(data, 98)
        first_x, first_y = seen[0]
        self.assertEqual(len(first_y), 252)
        # First fit at index301: features49..300, realized labels50..301.
        expected = (data.close / data.open - 1).iloc[50:302].to_numpy()
        np.testing.assert_allclose(first_y, expected)
        self.assertEqual(first_x.shape, (252, 5))
        self.assertLessEqual(len(seen), 10)  # Monthly, not 450 daily fits.

    def test_next_open_shift_with_positive_training_labels(self):
        data = market(400)
        data['open'] = data.close * .99
        data['low'] = data.open - .1
        signal = build_model_signal(data, 98)
        self.assertFalse(signal.want_long.iloc[301])
        self.assertTrue(signal.want_long.iloc[302])
        self.assertTrue(signal.want_long.iloc[302:].all())

    def test_mixture_deterministic_and_finite_on_flat_data(self):
        values = np.zeros(252)
        first = _fit_mixture(values)
        second = _fit_mixture(values)
        for left, right in zip(first, second):
            np.testing.assert_array_equal(left, right)
        probabilities = _posterior([0, .1, -.1], *first)
        self.assertTrue(np.isfinite(probabilities).all())
        np.testing.assert_allclose(probabilities.sum(axis=1), 1.)
        data = market(400)
        data.loc[:, ['open', 'close']] = 100.
        data['high'], data['low'] = 101., 99.
        for strategy in (98, 99):
            self.assertFalse(build_model_signal(data, strategy).want_long.any())

    def test_regime_posterior_controls_next_open_target(self):
        data = market(300)
        changes = np.full(300, .001)
        changes[260] = -.1
        data['close'] = 100 * np.cumprod(1 + changes)
        data['open'] = np.r_[100., data.close.to_numpy()[:-1]]
        data['high'] = data[['open', 'close']].max(axis=1) + .1
        data['low'] = data[['open', 'close']].min(axis=1) - .1
        mixture = (np.array([.5, .5]), np.array([.001, -.01]),
                   np.array([1e-6, .001]))
        with patch('research.policies.model_signals._fit_mixture', return_value=mixture):
            target = build_model_signal(data, 99).want_long
        self.assertTrue(target.iloc[253])
        self.assertTrue(target.iloc[260])  # Crash not yet observed at this open.
        self.assertFalse(target.iloc[261])
        self.assertTrue(target.iloc[262])

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            build_model_signal(market().iloc[::-1], 98)
        with self.assertRaises(ValueError):
            build_model_signal(market(), 100)


if __name__ == '__main__':
    unittest.main()
