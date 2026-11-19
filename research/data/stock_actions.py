"""Stock corporate actions from a Yahoo chart snapshot, in the etf-normalise actions format.

Rules (Plan 5, Task 1):

- Splits: an integer forward ratio >= 2 becomes a split record. A symbol with any other split
  (reverse, or a non-integer ratio such as 3:2) is excluded, with the reason.
- Dividends: Yahoo's amounts are adjusted for later splits. Each is multiplied back by the product
  of the ratios of that symbol's splits dated strictly after its ex-date, giving the raw amount.
- Yahoo gives no pay date, so ``pay_date = ex_date`` and every cash event carries the label
  ``pay_date_unknown_credited_on_ex_date``.
- Archive symbols use dots (BRK.B); Yahoo uses dashes (BRK-B). The archive symbol is the key and
  the mapping is recorded in the document.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from research.data.yahoo_snapshot import SYMBOL_RE, parse_chart

LABEL_PAY_DATE = "pay_date_unknown_credited_on_ex_date"
MICRO = Decimal("0.000001")


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def read_symbols_file(path) -> tuple[list[str], list[dict]]:
    """Return (valid archive symbols in file order, rejected [{symbol, reason}]) from a CSV."""
    valid, rejected, seen = [], [], set()
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            if not SYMBOL_RE.fullmatch(symbol) or not SYMBOL_RE.fullmatch(yahoo_symbol(symbol)):
                rejected.append({"symbol": symbol, "reason": "symbol fails SYMBOL_RE; not fetched"})
            elif symbol not in seen:
                seen.add(symbol)
                valid.append(symbol)
    return valid, rejected


def _ratio(item: dict) -> Decimal:
    return Decimal(repr(item["numerator"])) / Decimal(repr(item["denominator"]))


def _split_problem(splits: list[dict]) -> str | None:
    for item in splits:
        text = f"{item['numerator']}:{item['denominator']} on {item['date']}"
        ratio = _ratio(item)
        if ratio < 1:
            return f"reverse split {text}"
        if ratio != int(ratio) or ratio < 2:
            return f"non-integer or unit split ratio {text}"
    return None


def _plain(number: Decimal) -> str:
    text = format(number.quantize(MICRO).normalize(), "f")
    return text


def build_stock_actions(snapshot_manifest: dict, root: Path) -> tuple[dict, list[dict]]:
    root = Path(root)
    snapshot_id = snapshot_manifest["dataset_id"]
    cash, splits_out, excluded, symbol_map = [], [], [], {}
    received = set()
    for entry in snapshot_manifest["files"]:
        name = Path(entry["path"]).name
        if not (name.startswith("response-") and name.endswith(".json")):
            continue
        symbol = name[len("response-"):-len(".json")]
        received.add(symbol)
        request = yahoo_symbol(symbol)
        if request != symbol:
            symbol_map[symbol] = request
        _frame, dividends, splits = parse_chart((root / entry["path"]).read_bytes(), request)
        problem = _split_problem(splits)
        if problem:
            excluded.append({"symbol": symbol, "reason": problem})
            continue
        ratios = [(item["date"], int(_ratio(item))) for item in splits]
        for item in splits:
            ratio = int(_ratio(item))
            splits_out.append({"id": f"{symbol}-split-{item['date']}", "symbol": symbol, "kind": "split",
                               "ex_date": item["date"], "ratio": str(ratio)})
        for item in dividends:
            factor = 1
            for day, ratio in ratios:
                if day > item["date"]:
                    factor *= ratio
            amount = Decimal(repr(item["amount"])) * factor
            cash.append({"id": f"{symbol}-div-{item['date']}", "symbol": symbol, "kind": "cash",
                         "ex_date": item["date"], "pay_date": item["date"], "amount": _plain(amount),
                         "pay_date_label": LABEL_PAY_DATE})
    receipt = root / "raw" / "yahoo" / snapshot_id / "requests.json"
    if receipt.exists():
        for row in json.loads(receipt.read_text(encoding="utf-8")):
            if row["symbol"] not in received:
                reason = ("not attempted (run stopped)" if row["status"] == "not_attempted"
                          else f"fetch failed: {row.get('error')}")
                excluded.append({"symbol": row["symbol"], "reason": reason})
    cash.sort(key=lambda e: (e["ex_date"], e["symbol"]))
    splits_out.sort(key=lambda e: (e["ex_date"], e["symbol"]))
    doc = {"source": "yahoo chart events, un-adjusted for later splits", "snapshot_id": snapshot_id,
           "rights": snapshot_manifest["rights"], "labels": [LABEL_PAY_DATE],
           "symbol_map": dict(sorted(symbol_map.items())),
           "excluded_symbols": excluded, "cash_and_in_kind": cash, "splits": splits_out}
    return doc, excluded


def write_actions(path: Path, doc: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:  # exclusive create: never overwrite
        json.dump(doc, handle, indent=1)
        handle.write("\n")
    return path
