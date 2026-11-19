"""Parity comparator for two engine results.

Share quantities, fill dates and fill rows must match exactly; cash and equity
must agree within ``cash_tol_usd`` on every session. Mismatches name the
session, instrument (where applicable) and field.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from research.evaluation.engine_contract import EngineResult


@dataclass(frozen=True)
class ParityReport:
    passed: bool
    mismatches: tuple[str, ...]


def _equity_by_date(frame) -> dict[str, float]:
    return {str(d): float(v) for d, v in zip(frame["date"], frame["equity"])}


def _compare_money(out: list[str], field: str, a: dict[str, float], b: dict[str, float], tol: float) -> None:
    for day in sorted(set(a) | set(b)):
        if day not in a or day not in b:
            side = "first" if day not in a else "second"
            out.append(f"{day} {field}: session missing from {side} result")
        elif not (math.isfinite(a[day]) and math.isfinite(b[day])):
            out.append(f"{day} {field}: non-finite value {a[day]} vs {b[day]}")
        elif abs(a[day] - b[day]) > tol + 1e-9:
            out.append(f"{day} {field}: {a[day]:.2f} vs {b[day]:.2f}")


def _positions(frame) -> dict[tuple[str, str], int]:
    return {(str(d), str(n)): int(q) for d, n, q in zip(frame["date"], frame["instrument"], frame["quantity"])}


def _cents(price: float) -> int | None:
    """Integer cents for a cent-grid price; None when off the grid or non-finite."""
    p = float(price)
    if not math.isfinite(p) or abs(p * 100 - round(p * 100)) > 1e-6:
        return None
    return round(p * 100)


def _fills(frame, label: str, out: list[str]) -> set[tuple]:
    rows = set()
    for d, n, s, q, p in zip(frame["date"], frame["instrument"], frame["side"], frame["quantity"], frame["price"]):
        cents = _cents(p)
        if cents is None:
            out.append(f"{d} {n} fills price: {float(p)!r} is off the cent grid in {label} result")
            continue
        rows.add((str(d), str(n), str(s), int(q), cents))
    return rows


def compare(a: EngineResult, b: EngineResult, cash_tol_usd: float = 0.01) -> ParityReport:
    out: list[str] = []
    _compare_money(out, "equity", _equity_by_date(a.returns), _equity_by_date(b.returns), cash_tol_usd)
    _compare_money(
        out,
        "cash",
        {str(d): float(v) for d, v in a.cash.items()},
        {str(d): float(v) for d, v in b.cash.items()},
        cash_tol_usd,
    )

    pos_a, pos_b = _positions(a.positions), _positions(b.positions)
    for key in sorted(set(pos_a) | set(pos_b)):
        qa, qb = pos_a.get(key, 0), pos_b.get(key, 0)
        if qa != qb:
            out.append(f"{key[0]} {key[1]} positions quantity: {qa} vs {qb}")

    fills_a, fills_b = _fills(a.fills, "first", out), _fills(b.fills, "second", out)
    only_a, only_b = fills_a - fills_b, fills_b - fills_a
    by_a = {(d, n, s): (q, p) for d, n, s, q, p in only_a}
    by_b = {(d, n, s): (q, p) for d, n, s, q, p in only_b}
    # Same (date, instrument, side) filled differently: name the differing field.
    for key in sorted(set(by_a) & set(by_b)):
        (qa, pa), (qb, pb) = by_a[key], by_b[key]
        if pa != pb:
            out.append(f"{key[0]} {key[1]} fills price: {pa / 100:.2f} vs {pb / 100:.2f}")
        if qa != qb:
            out.append(f"{key[0]} {key[1]} fills quantity: {qa} vs {qb}")
    paired = set(by_a) & set(by_b)
    for d, n, s, q, p in sorted(only_a):
        if (d, n, s) not in paired:
            out.append(f"{d} {n} fills extra in first: {s} {q} @ price {p / 100:.2f}")
    for d, n, s, q, p in sorted(only_b):
        if (d, n, s) not in paired:
            out.append(f"{d} {n} fills extra in second: {s} {q} @ price {p / 100:.2f}")
    return ParityReport(not out, tuple(out))
