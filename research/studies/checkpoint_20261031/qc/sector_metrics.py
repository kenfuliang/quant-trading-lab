"""Pure summary metrics; intended to execute inside QC on its private NAV path."""
from datetime import date
import math
import statistics


def summarize_path(rows, opening, anchor_date):
    if not rows or opening <= 0:
        raise ValueError('Need positive opening NAV and observations')
    dates = [date.fromisoformat(d) for d, _ in rows]
    values = [float(v) for _, v in rows]
    anchor = date.fromisoformat(anchor_date)
    if dates[0] <= anchor or any(b <= a for a, b in zip(dates, dates[1:])):
        raise ValueError('Dates must increase strictly after anchor')
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('Nonpositive or nonfinite NAV')
    previous = peak = float(opening)
    peak_date = anchor
    drawdown = 0.0
    returns = []
    underwater = longest = run = longest_days = 0
    for d, v in zip(dates, values):
        returns.append(v / previous - 1)
        previous = v
        if v >= peak:
            peak = v
            peak_date = d
            run = 0
        else:
            run += 1
            underwater += 1
            longest = max(longest, run)
            # Calendar days peak to last underwater mark, excludes recovery day.
            longest_days = max(longest_days, (d - peak_date).days)
        drawdown = min(drawdown, v / peak - 1)
    sd = statistics.stdev(returns) if len(returns) > 1 else 0
    sharpe = statistics.mean(returns) / sd * math.sqrt(252) if sd > 1e-15 else None
    total = values[-1] / opening - 1
    cagr = (values[-1] / opening) ** (365.25 / (dates[-1] - anchor).days) - 1
    return dict(n=len(rows), end=values[-1], ret=total, cagr=cagr, dd=drawdown,
                sharpe=sharpe, calmar=cagr / abs(drawdown) if drawdown < 0 else None,
                annual_calmar=total / abs(drawdown) if drawdown < 0 else None,
                uw=underwater, uw_fraction=underwater / len(rows),
                longest_uw=longest, longest_uw_days=longest_days,
                censored=values[-1] < peak,
                return_sum=sum(returns), return_square_sum=sum(r*r for r in returns))
