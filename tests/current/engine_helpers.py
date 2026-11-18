"""Shared helpers for engine tests."""
from __future__ import annotations

from research.evaluation.market_model import Decision, TargetFn


def hold_targets(targets: dict[str, int]) -> TargetFn:
    """A TargetFn that returns the same targets and no signals every session."""

    def target_fn(session, bars, holdings, equity) -> Decision:
        return Decision(dict(targets), {})

    return target_fn
