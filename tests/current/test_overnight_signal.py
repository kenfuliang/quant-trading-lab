import unittest

import numpy as np
import pandas as pd

from research.policies.overnight_signal import build_overnight_signal


def bars(count=8):
    close = np.arange(count, dtype=float) + 100
    return pd.DataFrame({'open': close - .1, 'high': close + .3,
                         'low': close - .3, 'close': close},
                        index=pd.bdate_range('2004-01-02', periods=count))


class OvernightSignalTests(unittest.TestCase):
    def test_precommitted_shift_and_schedule(self):
        data = bars()
        result = build_overnight_signal(data)
        self.assertEqual(result.want_long.tolist(), [False] + [True] * 7)
        self.assertEqual(result.want_long.dtype, bool)
        self.assertEqual(result.execution_schedule.unique().tolist(), ['overnight'])
        pd.testing.assert_index_equal(result.index, data.index)
        pd.testing.assert_frame_equal(result[['open', 'low', 'close']], data[['open', 'low', 'close']])

    def test_prefix_determinism_and_current_prices_do_not_select_entry(self):
        data = bars()
        first = build_overnight_signal(data)
        pd.testing.assert_frame_equal(first, build_overnight_signal(data))
        pd.testing.assert_frame_equal(first.iloc[:5], build_overnight_signal(data.iloc[:5]))
        changed = data.copy()
        changed.iloc[3:, :] *= 2
        second = build_overnight_signal(changed)
        pd.testing.assert_series_equal(first.want_long, second.want_long)
        pd.testing.assert_frame_equal(first.iloc[:3], second.iloc[:3])

    def test_warmup_can_be_sliced_after_build(self):
        data = bars()
        self.assertTrue(build_overnight_signal(data).iloc[1:].want_long.all())
        self.assertFalse(build_overnight_signal(data.iloc[:1]).want_long.any())

    def test_invalid_input(self):
        valid = bars()
        for invalid in (valid.iloc[::-1], valid.iloc[:0], pd.concat([valid, valid.iloc[-1:]]),
                        valid.assign(open=np.nan), valid.assign(high=0), valid.assign(low=-1)):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    build_overnight_signal(invalid)
        with self.assertRaises(ValueError):
            build_overnight_signal(valid, 18)


if __name__ == '__main__':
    unittest.main()
