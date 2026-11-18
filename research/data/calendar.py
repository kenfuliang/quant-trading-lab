"""US ETF session calendar for the data layer (current code; mirrors the pinned legacy rules).

Same holiday rules, exceptional closures and early-close rules as the frozen
``research/us_etf_calendar.py``; a test compares the two for every day 2004-2025. The range
check stays 2004-01-01..2025-12-31 for now. Not venue certification.
"""
from functools import lru_cache

import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay,
                                    USMartinLutherKingJr, USMemorialDay, USPresidentsDay,
                                    USThanksgivingDay, nearest_workday, sunday_to_monday)

FIRST, LAST = "2004-01-01", "2025-12-31"


class Holidays(AbstractHolidayCalendar):
    rules = [Holiday("New Year", month=1, day=1, observance=sunday_to_monday),
             USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
             Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
             Holiday("Independence", month=7, day=4, observance=nearest_workday),
             USLaborDay, USThanksgivingDay,
             Holiday("Christmas", month=12, day=25, observance=nearest_workday)]


@lru_cache(maxsize=1)
def _all_sessions():
    holidays = Holidays().holidays(FIRST, LAST)
    exceptional = pd.to_datetime(["2004-06-11", "2007-01-02", "2012-10-29", "2012-10-30",
                                  "2018-12-05", "2025-01-09"])
    return pd.bdate_range(FIRST, LAST).difference(holidays.union(exceptional))


def sessions(start, end) -> pd.DatetimeIndex:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start < pd.Timestamp(FIRST) or end > pd.Timestamp(LAST) or start > end:
        raise ValueError("Calendar is qualified only for 2004-2025 research.")
    dates = _all_sessions()
    return dates[(dates >= start) & (dates <= end)]


def is_half_day(day) -> bool:
    day = pd.Timestamp(day)
    if day not in _all_sessions():
        raise ValueError("Not a session.")
    return bool((day.month == 11 and day.weekday() == 4 and 23 <= day.day <= 29) or
                (day.month == 12 and day.day == 24 and day.weekday() < 4) or
                (day.month == 7 and day.day == 3 and day.weekday() in (0, 1, 3)) or
                (day.month == 7 and day.day == 3 and day.weekday() == 2 and day.year >= 2013) or
                (day.month == 7 and day.day == 5 and day.weekday() == 4 and day.year < 2013))
