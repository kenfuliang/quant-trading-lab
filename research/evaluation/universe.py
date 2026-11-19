"""Point-in-time universe masking and the survivor-bias labels.

``members_only`` wraps a ``TargetFn``: on each decision date, names that are not index members on
THAT date get target 0. It never looks at a later date, so the mask is causal. The decision made
after the close of session t is traded at t+1, so membership is the one known at decision time.
"""
from __future__ import annotations

from research.data.membership import membership_on
from research.evaluation.market_model import Decision, TargetFn

# Every stock result built on the current-holdings proxy carries both labels (docs/goals.md).
LABELS = ("survivor-biased", "discovery-only")
UNIVERSE_SIGNAL = ("*", "universe")  # (instrument, stage); the value is the masked-name count


def members_only(target_fn: TargetFn, intervals_by_symbol: dict) -> TargetFn:
    """Set the targets of non-members to 0, using membership on the decision date only.

    ``intervals_by_symbol`` is ``{symbol: [{start, end|None}]}`` keyed by the names in the market
    data (see ``research.data.identity.intervals_for_dataset``). The wrapper adds the signal
    ``("*", "universe")`` = the number of names whose non-zero target it zeroed that session.
    """

    def masked(session: str, bars, holdings, equity) -> Decision:
        decision = target_fn(session, bars, holdings, equity)
        members = membership_on(intervals_by_symbol, session)
        targets, count = {}, 0
        for name, target in decision.targets.items():
            if name in members or not target:
                targets[name] = target
            else:
                targets[name] = 0
                count += 1
        signals = dict(decision.signals)
        signals[UNIVERSE_SIGNAL] = float(count)
        return Decision(targets=targets, signals=signals)

    return masked
