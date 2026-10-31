"""Pure, fixed GATE-RS1 selector; caller qualifies dates, actions and availability."""
import math
import statistics
from collections.abc import Mapping
from dataclasses import dataclass

UNIVERSE = ('TECL', 'SOXL', 'TQQQ', 'QQQ', 'SOXX', 'VTI')
FAMILY = dict(TECL='technology', SOXL='semiconductors', SOXX='semiconductors',
              TQQQ='nasdaq100', QQQ='nasdaq100', VTI='broad_us')
EQUAL_FAMILY = dict(TECL=.25, SOXL=.125, SOXX=.125, TQQQ=.125, QQQ=.125, VTI=.25)


def causal_window(records, *, cutoff, session):
    """Overfetch safely, then retain253 actually completed, dated bars.

    Records are (session ISO date, actual end timestamp, close). Overfetching
    cannot admit a future bar or replace a missing current completed session.
    """
    eligible = [(str(day), end, float(close)) for day, end, close in records
                if end <= cutoff and str(day) <= session]
    dates = [day for day, _, _ in eligible]
    if len(set(dates)) != len(dates) or dates != sorted(dates):
        raise ValueError('Duplicate/unordered completed sessions')
    if len(eligible) < 253 or eligible[-1][0] != session:
        raise ValueError('Insufficient/current completed history missing')
    eligible = eligible[-253:]
    return [r[0] for r in eligible], [r[2] for r in eligible]


def align_histories(histories, *, cutoff, allowed_latest):
    """Common completed253-session panel; latest date must be explicitly allowed.

    Caller supplies current and prior exchange session, not calendar-day guesses.
    A lagged result is recorded rather than imputed or called current-session.
    """
    if set(histories) != set(UNIVERSE) or not allowed_latest:
        raise ValueError('Missing declared history or calendar availability bound')
    panels = {}
    for ticker, records in histories.items():
        valid = [(str(d), float(v)) for d, end, v in records if end <= cutoff and str(d) <= max(allowed_latest)]
        dates = [d for d, _ in valid]
        if dates != sorted(dates) or len(set(dates)) != len(dates):
            raise ValueError('Duplicate/unordered history')
        panels[ticker] = dict(valid)
    common = sorted(set.intersection(*(set(p) for p in panels.values())))
    if len(common) < 253 or common[-1] not in allowed_latest:
        raise ValueError('Insufficient or stale common completed history')
    dates = common[-253:]
    return dates, {t: [panels[t][d] for d in dates] for t in UNIVERSE}


@dataclass(frozen=True)
class RankedETF:
    ticker: str
    momentum: float
    volatility: float
    score: float | None
    eligible: bool


@dataclass(frozen=True)
class Proposal:
    weights: tuple[tuple[str, float], ...]
    ranking: tuple[RankedETF, ...]


def select(closes: Mapping) -> Proposal:
    """Consume exactly253 qualified common-session TR closes per actual ETF.

    Missing/invalid input raises. Undefined volatility is ineligible, never an
    infinite score. A sole winner retains only one half-budget; cash is residual.
    No gate, reserve, future outcome or execution state is consumed here.
    """
    if not isinstance(closes, Mapping) or set(closes) != set(UNIVERSE):
        raise ValueError('Need exactly the six declared ETF histories')
    rows = []
    for ticker in UNIVERSE:
        values = list(closes[ticker])
        if len(values) != 253:
            raise ValueError('Need exactly253 completed common-session closes')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError('Total-return closes must be positive finite numbers')
        momentum = values[-1] / values[0] - 1
        returns = [b / a - 1 for a, b in zip(values[-64:-1], values[-63:])]
        vol = statistics.stdev(returns) * math.sqrt(252)
        if not math.isfinite(momentum) or not math.isfinite(vol):
            raise ValueError('Feature overflow')
        score = momentum / vol if vol > 1e-12 else None
        if score is not None and not math.isfinite(score):
            raise ValueError('Score overflow')
        rows.append(RankedETF(ticker, momentum, vol, score,
                              momentum > 0 and score is not None))
    ranked = sorted(rows, key=lambda r: (not r.eligible,
                    -r.score if r.score is not None else 0, r.ticker))
    used, weights = set(), []
    for row in ranked:
        family = FAMILY[row.ticker]
        if row.eligible and family not in used and len(weights) < 2:
            weights.append((row.ticker, .5))
            used.add(family)
    return Proposal(tuple(weights), tuple(ranked))
