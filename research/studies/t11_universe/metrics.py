"""Small cloud-compatible closing-path summary, independently checked locally."""
import math
import statistics
from datetime import date


def summarize(rows, initial=10000., anchor='2019-12-31'):
    """Recovery-inclusive longest episode; annual rows use prior year close."""
    path = [(date.fromisoformat(anchor), float(initial))]
    for session, value in rows:
        day = date.fromisoformat(str(session))
        value = float(value)
        if day <= path[-1][0] or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid, duplicate or unordered NAV path')
        path.append((day, value))
    if len(path) < 2 or initial <= 0:
        raise ValueError('Need anchored positive NAV')
    returns = [b[1]/a[1]-1 for a, b in zip(path, path[1:])]
    peak = path[0][1]
    peak_i = 0
    start = None
    deepest = 0.
    episodes = []
    for i, (day, value) in enumerate(path[1:], 1):
        if value >= peak:
            if start is not None:
                episodes.append((i-start, (day-path[start][0]).days, False))
                start = None
            peak, peak_i = value, i
        else:
            if start is None:
                start = peak_i
            deepest = min(deepest, value/peak-1)
    if start is not None:
        episodes.append((len(path)-1-start, (path[-1][0]-path[start][0]).days, True))
    longest = max(episodes, default=(0, 0, False), key=lambda e: (e[0], e[1]))
    growth = (path[-1][1]/initial)**(365.25/(path[-1][0]-path[0][0]).days)-1
    sd = statistics.stdev(returns) if len(returns) > 1 else 0.
    return dict(n=len(rows), end=path[-1][1], cagr=growth, dd=deepest,
                calmar=growth/abs(deepest) if deepest < 0 else None,
                sharpe=statistics.mean(returns)/sd*math.sqrt(252) if sd > 1e-15 else None,
                longest_sessions=longest[0], longest_days=longest[1],
                longest_censored=longest[2], temporal='recovery-inclusive-v1.2')


def annual(rows, initial=10000., anchor='2019-12-31'):
    result = []
    opening = initial
    for year in sorted({str(d)[:4] for d, _ in rows}):
        subset = [(d, v) for d, v in rows if str(d).startswith(year)]
        row = summarize(subset, opening, anchor)
        row['year'] = year
        row['return'] = subset[-1][1]/opening-1
        row['annual_calmar'] = row['return']/abs(row['dd']) if row['dd'] < 0 else None
        result.append(row)
        anchor, opening = str(subset[-1][0]), subset[-1][1]
    return result
