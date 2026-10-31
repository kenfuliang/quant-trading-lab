"""Project an upstream T11 allocation into SOXL or cash.

Consumes upstream decisions without reproducing third-party strategy logic.
Output is an intent at the input decision time, not a fill or daily rebalance.
The existing execution controller must apply the reserve only once.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Selection:
    soxl_target_nav: float
    cash_target_nav: float
    reason: str


def select(base_weights: Mapping[str, float], *, ready: bool, gate_cap: float,
           allocation: float = 0.9) -> Selection:
    """Concentrate only a SOXL-eligible T11 branch; other branches become cash.

    ``base_weights`` must precede the gate. ``gate_cap`` is the unchanged
    upstream gate's normalized cap; unknown/unassessed must be supplied as zero.
    Cash is the unallocated target, not an assertion about actual account cash.
    """
    if type(ready) is not bool:
        raise ValueError('ready must be an explicit boolean')
    for name, value in (('gate_cap', gate_cap), ('allocation', allocation)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f'{name} must be finite and within [0, 1]')
    if gate_cap not in (0, 0.5, 1):
        raise ValueError('gate_cap must preserve the existing discrete gate')
    weights = dict(base_weights)
    for symbol, weight in weights.items():
        if not isinstance(symbol, str) or not symbol:
            raise ValueError('invalid symbol')
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError('base weights must be finite long-only fractions')
    if sum(weights.values()) > 1 + 1e-12:
        raise ValueError('base weights exceed normalized allocation')
    if not ready:
        return Selection(0., 1., 'not_ready')
    if weights.get('SOXL', 0) <= 0:
        return Selection(0., 1., 't11_not_soxl_eligible')
    target = allocation * gate_cap
    return Selection(target, 1 - target, 'gate_cash' if target == 0 else 'soxl_eligible')
