"""Daily pandas screening engine over ``MarketData`` (raw, unadjusted prices).

Timing: the decision made at the close of session t fills at the open of t+1.

Per-session order (a contract; the NautilusTrader engine reproduces it exactly):

1. Split effective on d: held quantity x ratio and no cash moves (a whole-share forward
   split creates no fractional share, so there is no cash in lieu); any pending target
   for that instrument is scaled by the ratio. No fill is recorded.
2. Dividends with ``pay_date == d``: credit ``round(per_share * shares, 2)`` where shares
   are those held at the close of the session before ``ex_date``.
3. Orders from the decision made at close d-1: the order is target minus current holding
   (zero means no order). Sells first, then buys, each sorted by instrument name. Fill
   price ``execution_price(open, side, bps)`` with ``bps = cost_bps(data, n, i - 1, config)``
   (flat ``config.cost_bps``, or the ADV tier from sessions i-21..i-2: strictly before the
   decision session i-1); commission per fill; fill
   ``cost = commission + |price - open| * quantity``. Overspend rule: after all sells have
   filled, buys are processed in order and a buy that would leave
   ``cash - (price * quantity + commission) < 0`` raises ``EngineError`` (never skipped
   or partially filled).
4. Close mark: equity = cash + sum(quantity x close). ``net_return = equity / previous
   equity - 1`` (previous equity is ``initial_cash`` on the first session),
   ``cost = session fill costs / previous equity``, ``gross_return = net_return + cost``.
   Positions: one row per (session, instrument held with non-zero quantity), weight =
   value / equity. Cash is recorded per session.
5. Decision for d+1 (not on the last session): ``target_fn(d, history_view(data, d),
   holdings, equity)`` (bars up to and including d with a causal ``split_factor``) where holdings maps every instrument to its integer quantity
   (zeros included). Targets pass ``engine_contract.checked_targets``: unknown
   instruments, negative, bool, non-finite or non-integral share counts raise
   ``EngineError`` (never truncated). Signals are recorded with date d. Instruments absent
   from the targets are treated as target 0.

``config`` is checked by ``engine_contract.check_config`` before the run.

Dates are 'YYYY-MM-DD' strings. Values keep full float precision.
"""
from __future__ import annotations

from research.evaluation.engine_contract import (
    EngineError,
    EngineResult,
    build_result,
    check_buy,
    check_config,
    checked_targets,
    mark,
)
from research.evaluation.market_model import (
    MarketConfig,
    MarketData,
    TargetFn,
    cost_table,
    execution_price,
    history_view,
    validate,
)

__all__ = ["EngineError", "EngineResult", "run_screen"]  # EngineError/EngineResult re-exported for callers


def run_screen(data: MarketData, target_fn: TargetFn, config: MarketConfig) -> EngineResult:
    validate(data)
    check_config(config)
    sessions = list(data.sessions)
    names = sorted(data.bars)
    cols = {n: {c: data.bars[n][c].to_numpy() for c in ("open", "close")} for n in names}
    bps = cost_table(data, config)  # bps[n][i - 1]: tier at the decision session, for the fill at i
    cash = float(config.initial_cash)
    qty = {n: 0 for n in names}
    pending: dict[str, int] | None = None
    close_qty: list[dict[str, int]] = []  # holdings at each session close
    marks, signals, fills = [], [], []

    for i, day in enumerate(sessions):
        # 1. splits
        for split in data.splits:
            if split.effective_date != day:
                continue
            n, ratio = split.instrument, split.ratio
            qty[n] = qty[n] * ratio  # a whole-share forward split moves no cash
            if pending is not None and n in pending:
                pending[n] = pending[n] * ratio
        # 2. dividends
        for div in data.dividends:
            if div.pay_date != day:
                continue
            ex_idx = sessions.index(div.ex_date)
            held = close_qty[ex_idx - 1][div.instrument] if ex_idx > 0 else 0
            cash += round(div.per_share * held, 2)
        # 3. orders
        if pending is not None:
            diffs = {n: pending.get(n, 0) - qty[n] for n in names}
            ordered = [("SELL", n, -d) for n, d in diffs.items() if d < 0]
            ordered += [("BUY", n, d) for n, d in diffs.items() if d > 0]
            for side, n, q in ordered:
                open_px = float(cols[n]["open"][i])
                price = execution_price(open_px, side, float(bps[n][i - 1]))
                value = price * q
                if side == "SELL":
                    cash += value - config.commission_usd
                    qty[n] -= q
                else:
                    cash = check_buy(day, n, q, price, cash, config.commission_usd)
                    qty[n] += q
                fills.append((day, n, side, q, price, config.commission_usd + abs(price - open_px) * q))
        # 4. close mark
        marks.append(mark(day, cash, qty, {n: float(cols[n]["close"][i]) for n in names}))
        close_qty.append(dict(qty))
        # 5. decision
        if i < len(sessions) - 1:
            decision = target_fn(day, history_view(data, i), dict(qty), marks[-1]["equity"])
            try:
                pending = checked_targets(decision, names)
            except EngineError as exc:
                raise EngineError(f"{day}: {exc}") from None
            for (n, stage), value in decision.signals.items():
                signals.append((day, n, stage, float(value)))

    return build_result("screen", marks, fills, signals, config.initial_cash)
