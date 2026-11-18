"""Daily pandas screening engine over ``MarketData`` (raw, unadjusted prices).

Timing: the decision made at the close of session t fills at the open of t+1.

Per-session order (a contract; the NautilusTrader engine reproduces it exactly):

1. Split effective on d: held quantity x ratio; cash in lieu
   ``q * prev_close - q * ratio * round(prev_close / ratio, 2)`` (only when q > 0);
   any pending target for that instrument is scaled by the ratio. No fill is recorded.
2. Dividends with ``pay_date == d``: credit ``per_share`` x shares held at the close of
   the session before ``ex_date``.
3. Orders from the decision made at close d-1: the order is target minus current holding
   (zero means no order). Sells first, then buys, each sorted by instrument name. Fill
   price ``execution_price(open, side, cost_bps)``; commission per fill; fill
   ``cost = commission + |price - open| * quantity``. Overspend rule: after all sells have
   filled, buys are processed in order and a buy that would leave
   ``cash - (price * quantity + commission) < 0`` raises ``EngineError`` (never skipped
   or partially filled).
4. Close mark: equity = cash + sum(quantity x close). ``net_return = equity / previous
   equity - 1`` (previous equity is ``initial_cash`` on the first session),
   ``cost = session fill costs / previous equity``, ``gross_return = net_return + cost``.
   Positions: one row per (session, instrument held with non-zero quantity), weight =
   value / equity. Cash is recorded per session.
5. Decision for d+1 (not on the last session): ``target_fn(d, bars up to and including d,
   holdings, equity)`` where holdings maps every instrument to its integer quantity
   (zeros included). Unknown instruments or negative shares raise ``EngineError``. Signals
   are recorded with date d. Instruments absent from the targets are treated as target 0.

Dates are 'YYYY-MM-DD' strings. Values keep full float precision.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from research.evaluation.market_model import MarketConfig, MarketData, TargetFn, execution_price, validate
from research.evaluation.run_output import COLUMNS


class EngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class EngineResult:
    engine: str
    returns: pd.DataFrame
    positions: pd.DataFrame
    signals: pd.DataFrame
    fills: pd.DataFrame
    cash: pd.Series


def run_screen(data: MarketData, target_fn: TargetFn, config: MarketConfig) -> EngineResult:
    validate(data)
    sessions = list(data.sessions)
    names = sorted(data.bars)
    cols = {n: {c: data.bars[n][c].to_numpy() for c in ("open", "close")} for n in names}
    cash = float(config.initial_cash)
    qty = {n: 0 for n in names}
    pending: dict[str, int] | None = None
    close_qty: list[dict[str, int]] = []  # holdings at each session close
    prev_equity = float(config.initial_cash)
    returns, positions, signals, fills, cash_rows = [], [], [], [], []

    for i, day in enumerate(sessions):
        # 1. splits
        for split in data.splits:
            if split.effective_date != day:
                continue
            n, ratio = split.instrument, split.ratio
            q = qty[n]
            if q > 0:
                prev_close = float(cols[n]["close"][i - 1]) if i > 0 else float(cols[n]["open"][i])
                cash += q * prev_close - q * ratio * round(prev_close / ratio, 2)
            qty[n] = q * ratio
            if pending is not None and n in pending:
                pending[n] = pending[n] * ratio
        # 2. dividends
        for div in data.dividends:
            if div.pay_date != day:
                continue
            ex_idx = sessions.index(div.ex_date)
            held = close_qty[ex_idx - 1][div.instrument] if ex_idx > 0 else 0
            cash += div.per_share * held
        # 3. orders
        session_cost = 0.0
        if pending is not None:
            diffs = {n: pending.get(n, 0) - qty[n] for n in names}
            ordered = [("SELL", n, -d) for n, d in diffs.items() if d < 0]
            ordered += [("BUY", n, d) for n, d in diffs.items() if d > 0]
            for side, n, q in ordered:
                open_px = float(cols[n]["open"][i])
                price = execution_price(open_px, side, config.cost_bps)
                value = price * q
                if side == "SELL":
                    cash += value - config.commission_usd
                    qty[n] -= q
                else:
                    if cash - (value + config.commission_usd) < 0:
                        raise EngineError(f"{day}: buy {q} {n} @ {price} overspends cash {cash:.2f}")
                    cash -= value + config.commission_usd
                    qty[n] += q
                cost = config.commission_usd + abs(price - open_px) * q
                session_cost += cost
                fills.append((day, n, side, q, price, cost))
        # 4. close mark
        values = {n: qty[n] * float(cols[n]["close"][i]) for n in names}
        equity = cash + sum(values.values())
        net = equity / prev_equity - 1
        cost_frac = session_cost / prev_equity
        returns.append((day, net + cost_frac, cost_frac, net, equity))
        for n in names:
            if qty[n] != 0:
                positions.append((day, n, qty[n], values[n] / equity))
        cash_rows.append(cash)
        close_qty.append(dict(qty))
        prev_equity = equity
        # 5. decision
        if i < len(sessions) - 1:
            bars = {n: data.bars[n].iloc[: i + 1] for n in names}
            decision = target_fn(day, bars, dict(qty), equity)
            for n, shares in decision.targets.items():
                if n not in data.bars:
                    raise EngineError(f"{day}: target for unknown instrument {n!r}")
                if shares < 0:
                    raise EngineError(f"{day}: negative target {shares} for {n}")
            pending = {n: int(s) for n, s in decision.targets.items()}
            for (n, stage), value in decision.signals.items():
                signals.append((day, n, stage, float(value)))

    def frame(name: str, rows: list) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=list(COLUMNS[name]))

    return EngineResult(
        engine="screen",
        returns=frame("returns", returns),
        positions=frame("positions", positions),
        signals=frame("signals", signals),
        fills=frame("fills", fills),
        cash=pd.Series(cash_rows, index=pd.Index(sessions, name="date"), name="cash", dtype=float),
    )
