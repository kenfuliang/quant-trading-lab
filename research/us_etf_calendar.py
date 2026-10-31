"""Research session calendar restricted to 2004–2025, with independent fixture checks.

Rule source: exchange_calendars XNYS/us_holidays (Apache-2.0), saved under the
qualification epoch. This project implementation uses pandas public holiday rules;
no upstream module is executed or copied into site-packages. Not venue certification.
"""
import pandas as pd
from functools import lru_cache
from pandas.tseries.holiday import (AbstractHolidayCalendar, Holiday, GoodFriday,
    USMartinLutherKingJr, USPresidentsDay, USMemorialDay, USLaborDay,
    USThanksgivingDay, nearest_workday, sunday_to_monday)


class Holidays(AbstractHolidayCalendar):
    rules = [Holiday('New Year', month=1, day=1, observance=sunday_to_monday),
             USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
             Holiday('Juneteenth', month=6, day=19, start_date='2022-01-01', observance=nearest_workday),
             Holiday('Independence', month=7, day=4, observance=nearest_workday),
             USLaborDay, USThanksgivingDay,
             Holiday('Christmas', month=12, day=25, observance=nearest_workday)]


@lru_cache(maxsize=1)
def _all_sessions():
    holidays = Holidays().holidays('2004-01-01', '2025-12-31')
    exceptional = pd.to_datetime(['2004-06-11','2007-01-02','2012-10-29','2012-10-30','2018-12-05','2025-01-09'])
    return pd.bdate_range('2004-01-01', '2025-12-31').difference(holidays.union(exceptional))


def sessions(start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start < pd.Timestamp('2004-01-01') or end > pd.Timestamp('2025-12-31') or start > end:
        raise ValueError('Calendar is qualified only for2004–2025 research.')
    dates = _all_sessions()
    return dates[(dates >= start) & (dates <= end)]


def clocks(day):
    """NYSE-style regular/open/early-close clocks for these US ETF fixtures."""
    day = pd.Timestamp(day)
    if day not in _all_sessions():
        raise ValueError('Not a session.')
    early = ((day.month == 11 and day.weekday() == 4 and 23 <= day.day <= 29) or
             (day.month == 12 and day.day == 24 and day.weekday() < 4) or
             (day.month == 7 and day.day == 3 and day.weekday() in (0,1,3)) or
             (day.month == 7 and day.day == 3 and day.weekday() == 2 and day.year >= 2013) or
             (day.month == 7 and day.day == 5 and day.weekday() == 4 and day.year < 2013))
    date = day.strftime('%Y-%m-%d')
    return (pd.Timestamp(date+' 09:30', tz='America/New_York').tz_convert('UTC'),
            pd.Timestamp(date+(' 13:00' if early else ' 16:00'), tz='America/New_York').tz_convert('UTC'))
