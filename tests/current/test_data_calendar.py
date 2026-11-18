import unittest

import pandas as pd

from research import us_etf_calendar as frozen
from research.data import calendar as current


class CalendarParityTests(unittest.TestCase):
    def test_sessions_match_frozen_calendar(self):
        a = current.sessions("2004-01-01", "2025-12-31")
        b = frozen.sessions("2004-01-01", "2025-12-31")
        self.assertTrue(a.equals(b))
        self.assertGreater(len(a), 5000)

    def test_half_days_match_frozen_clocks_for_every_session(self):
        for day in frozen.sessions("2004-01-01", "2025-12-31"):
            opened, closed = frozen.clocks(day)
            early = closed - opened < pd.Timedelta(hours=6)
            self.assertEqual(current.is_half_day(day), early, day)

    def test_non_session_and_range_errors(self):
        with self.assertRaises(ValueError):
            current.is_half_day("2024-01-01")
        with self.assertRaises(ValueError):
            current.sessions("2003-12-31", "2004-01-05")
        with self.assertRaises(ValueError):
            current.sessions("2025-12-01", "2026-01-05")


if __name__ == "__main__":
    unittest.main()
