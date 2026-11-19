"""Instrument identity across ticker changes, and index coverage per date.

``instrument-identity/v1`` gives every symbol of the membership table (and every archive symbol)
one ``instrument_id`` with dated symbol intervals:

* a current archive member keeps its ``issuer_identifier`` (CUSIP-like) as id;
* a historical-only symbol gets ``sym:<SYMBOL>`` (a trailing ``-YYYYMM`` delisting suffix is
  stripped for the id; the raw source string stays an alias);
* a ticker change from the committed, sourced ``research/registry/ticker-changes.json`` joins the
  old symbol to the new symbol's instrument, ending the old symbol the day before the change.

Nothing here guesses a rename: an adjacent exit and entry in the membership table is only listed
as an unresolved candidate until a change record with a source exists.
"""
from __future__ import annotations

import json
import statistics
from datetime import date, timedelta
from pathlib import Path

from research.data.manifest import ManifestError, check_dataset_id
from research.data.membership import membership_on, norm

SCHEMA = "instrument-identity/v1"
COVERAGE_SCHEMA = "membership-coverage/v1"
KEYS = ("schema", "identity_id", "created_utc", "inputs", "instruments", "symbol_map", "ticker_changes",
        "unresolved_candidates", "counts", "cross_checks", "notes")
CAP = 25


def _next_day(day: str) -> str:
    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def _prev_day(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()


def check_ticker_changes(changes) -> list:
    """Validate ``[{old, new, date, source_url, ...}]``; every entry needs a cited source.

    ``source_url`` is a non-empty string; it may be ``None`` only with ``verified`` false and a plain
    ``source_note`` (a URL is never invented).
    """
    if not isinstance(changes, list):
        raise ValueError("ticker changes must be a list")
    for item in changes:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k] for k in ("old", "new", "date")):
            raise ValueError(f"ticker change needs old, new, date: {item!r}")
        date.fromisoformat(item["date"])
        url, note = item.get("source_url"), item.get("source_note")
        if isinstance(url, str) and url.startswith("https://"):
            continue
        if url is None and item.get("verified") is False and isinstance(note, str) and note:
            continue
        raise ValueError(f"ticker change {item['old']}->{item['new']} has no cited source")
    return changes


def load_ticker_changes(path) -> list:
    return check_ticker_changes(json.loads(Path(path).read_text(encoding="utf-8")))


def _add(symbol_map: dict, symbol: str, instrument_id: str, start, end) -> None:
    symbol_map.setdefault(symbol, []).append({"id": instrument_id, "start": start, "end": end})


def build_identity(archive_manifest: dict, membership: dict, ticker_changes: list) -> dict:
    """The identity table from the archive manifest (``universe.equities``), a ``membership/v1``
    document and the sourced ticker changes. Pure: no clock, no I/O."""
    check_ticker_changes(ticker_changes)
    intervals = membership["intervals"]
    instruments, symbol_map, archive_id = {}, {}, {}
    for equity in archive_manifest["universe"]["equities"]:
        symbol, instrument_id = equity["symbol"].strip().upper(), equity["issuer_identifier"]
        archive_id[norm(symbol)] = instrument_id
        entry = instruments.setdefault(instrument_id, {"kind": "current", "name": equity.get("name"),
                                                       "symbols": [], "aliases": []})
        if symbol not in entry["symbols"]:
            entry["symbols"].append(symbol)
        _add(symbol_map, symbol, instrument_id, None, None)
    for raw in sorted(intervals):
        base = norm(raw)
        if base in archive_id:
            instrument_id = archive_id[base]
        else:
            instrument_id = f"sym:{base}"
            instruments.setdefault(instrument_id, {"kind": "historical", "name": None, "symbols": [], "aliases": []})
        entry = instruments[instrument_id]
        if raw not in symbol_map:
            _add(symbol_map, raw, instrument_id, None, None)
        if base not in symbol_map:  # a suffixed raw string is also reachable by its plain symbol
            _add(symbol_map, base, instrument_id, None, None)
        if raw not in entry["symbols"]:
            entry["symbols"].append(raw)
        if raw != base and raw not in entry["aliases"]:
            entry["aliases"].append(raw)

    applied, unapplied = [], []
    for change in sorted(ticker_changes, key=lambda c: (c["date"], c["old"])):
        old, new = change["old"].strip().upper(), change["new"].strip().upper()
        record = {k: change[k] for k in change}
        if new not in symbol_map or old not in symbol_map:
            unapplied.append({**record, "reason": "old or new symbol is not in the archive or membership table"})
            continue
        new_id, old_id = symbol_map[new][-1]["id"], symbol_map[old][-1]["id"]
        if new_id != old_id:  # the old symbol's id folds into the new symbol's instrument
            old_entry = instruments.pop(old_id)
            target = instruments[new_id]
            target["symbols"].extend(s for s in old_entry["symbols"] if s not in target["symbols"])
            target["aliases"].extend(a for a in old_entry["aliases"] if a not in target["aliases"])
            for spans in symbol_map.values():
                for span in spans:
                    if span["id"] == old_id:
                        span["id"] = new_id
        symbol_map[old] = [dict(span, end=_prev_day(change["date"])) for span in symbol_map[old]]
        symbol_map[new] = [dict(span, start=change["date"]) for span in symbol_map[new]]
        applied.append(record)

    ids_by_symbol = {symbol: spans[-1]["id"] for symbol, spans in symbol_map.items()}
    unresolved = unresolved_candidates(intervals, ids_by_symbol, applied)
    counts = {"current_ids": sum(1 for v in instruments.values() if v["kind"] == "current"),
              "historical_only_ids": sum(1 for v in instruments.values() if v["kind"] == "historical"),
              "aliases": sum(len(v["aliases"]) for v in instruments.values()) + len(applied),
              "symbols": len(symbol_map), "ticker_changes_applied": len(applied),
              "ticker_changes_unapplied": len(unapplied), "unresolved_candidates": len(unresolved)}
    instruments = {k: {**v, "symbols": sorted(v["symbols"]), "aliases": sorted(v["aliases"])}
                   for k, v in sorted(instruments.items())}
    return {"schema": SCHEMA, "identity_id": None, "created_utc": None,
            "inputs": {"archive_dataset_id": archive_manifest.get("dataset_id"),
                       "membership_id": membership.get("membership_id")},
            "instruments": instruments, "symbol_map": dict(sorted(symbol_map.items())),
            "ticker_changes": {"applied": applied, "unapplied": unapplied},
            "unresolved_candidates": unresolved, "counts": counts, "cross_checks": [],
            "notes": ("current ids are archive issuer identifiers; historical-only symbols are sym:<SYMBOL> "
                      "(a -YYYYMM suffix is stripped for the id and kept as an alias). A ticker change ends the "
                      "old symbol the day before its date and starts the new symbol on it. Ticker reuse by a "
                      "different company is not detected. unresolved_candidates are one-to-one exit/entry "
                      "pairs one day apart in the membership table: most are ordinary index replacements, "
                      "so none is treated as a rename without a sourced record.")}


def unresolved_candidates(intervals: dict, ids_by_symbol: dict, applied: list) -> list:
    """Exit/entry pairs one day apart that are the only exit and only entry on their dates.

    Heuristic only: an ordinary one-for-one replacement looks identical to a rename. Pairs already
    covered by an applied ticker change are left out.
    """
    exits, entries = {}, {}
    for symbol, spans in intervals.items():
        for span in spans:
            if span["end"]:
                exits.setdefault(_next_day(span["end"]), []).append(symbol)
            entries.setdefault(span["start"], []).append(symbol)
    done = {(c["old"].upper(), c["new"].upper()) for c in applied}
    out = []
    for day in sorted(exits):
        for entry_day in (day, _next_day(day)):
            old, new = exits[day], entries.get(entry_day, [])
            if len(old) == 1 and len(new) == 1 and (old[0], new[0]) not in done \
                    and ids_by_symbol.get(old[0]) != ids_by_symbol.get(new[0]):
                out.append({"old": old[0], "new": new[0], "old_last_member_day": _prev_day(day), "new_first_member_day": entry_day})
    return out


def resolve(identity: dict, symbol: str, day: str):
    """The ``instrument_id`` that ``symbol`` denotes on ``day`` (ISO date), or ``None``.

    Exact (upper-cased) source string first, then its normalised form (delisting suffix dropped).
    """
    key = symbol.strip().upper()
    spans = identity["symbol_map"].get(key) or identity["symbol_map"].get(norm(key)) or ()
    for span in spans:
        if (span["start"] is None or span["start"] <= day) and (span["end"] is None or day <= span["end"]):
            return span["id"]
    return None


def current_id(identity: dict, symbol: str):
    """The instrument of an archive (dataset) symbol: its latest symbol interval, regardless of date."""
    key = symbol.strip().upper()
    spans = identity["symbol_map"].get(key) or identity["symbol_map"].get(norm(key)) or ()
    return spans[-1]["id"] if spans else None


def _ids_on(intervals: dict, identity: dict, day: str) -> set:
    return {resolve(identity, s, day) or f"unresolved:{s}" for s in membership_on(intervals, day)}


def coverage(membership: dict, identity: dict, dataset_symbols, sessions) -> dict:
    """Per session: index members (instruments), how many have data in the dataset, and the share."""
    intervals = membership["intervals"]
    have = {current_id(identity, s) for s in dataset_symbols} - {None}
    per_date = {}
    for day in sessions:
        ids = _ids_on(intervals, identity, day)
        with_data = len(ids & have)
        per_date[day] = {"in_index": len(ids), "with_data": with_data,
                         "share": with_data / len(ids) if ids else None}
    rated = [(item["share"], day) for day, item in per_date.items() if item["share"] is not None]
    if not rated:
        summary = {"sessions": len(per_date), "min_share": None, "median_share": None, "worst_dates": []}
    else:
        worst = sorted(rated)[:5]
        summary = {"sessions": len(per_date), "min_share": worst[0][0],
                   "median_share": statistics.median(share for share, _ in rated),
                   "worst_dates": [{"date": day, "share": share, "in_index": per_date[day]["in_index"],
                                    "with_data": per_date[day]["with_data"]} for share, day in worst]}
    return {"schema": COVERAGE_SCHEMA, "membership_id": membership.get("membership_id"),
            "identity_id": identity.get("identity_id"), "dataset_symbols": len(set(dataset_symbols)),
            "per_date": per_date, "summary": summary,
            "notes": "with_data assumes every dataset symbol has full-window bars (the stock dataset keeps "
                     "structural_full_window names only); it counts instruments, not bars present on the date."}


def intervals_for_dataset(membership: dict, identity: dict, dataset_symbols) -> dict:
    """Membership spans keyed by dataset symbol, with every alias (e.g. FB for META) folded in."""
    by_id = {}
    for symbol in dataset_symbols:
        instrument_id = current_id(identity, symbol)
        if instrument_id is not None:
            by_id.setdefault(instrument_id, []).append(symbol)
    spans_by_symbol = {}
    for raw, spans in membership["intervals"].items():
        for span in spans:
            instrument_id = resolve(identity, raw, span["start"])
            if instrument_id is None:
                raise ValueError(f"identity {identity.get('identity_id')} cannot resolve membership symbol {raw} "
                                 f"on {span['start']} (span {span}); the identity does not match this membership")
            for symbol in by_id.get(instrument_id, ()):
                spans_by_symbol.setdefault(symbol, []).append(dict(span))
    merged = {}
    for symbol, spans in spans_by_symbol.items():
        out = []
        for span in sorted(spans, key=lambda s: s["start"]):
            if out and out[-1]["end"] is not None and span["start"] <= _next_day(out[-1]["end"]):
                out[-1]["end"] = None if span["end"] is None else max(out[-1]["end"], span["end"])
            else:
                out.append(dict(span))
        merged[symbol] = out
    return merged


def cross_check_resolved(membership: dict, identity: dict, other_by_date: dict, one_sided=None, cap: int = CAP) -> dict:
    """Per date: instruments in only one of the two sources, with names resolved through the identity.

    ``one_sided`` is an optional ``{date: [symbols known to be members]}`` for a survivors-only source
    (the primary table is only checked for those). The other source's symbols resolve on the date, else
    to their latest instrument; symbols the identity does not know compare as ``sym:<norm>``.
    """
    intervals, result = membership["intervals"], {}

    def theirs_id(symbol, day):
        # Another source names a company by one ticker across its history (often today's), so a symbol
        # that is not valid on that date still denotes its instrument: naming is not a membership difference.
        return resolve(identity, symbol, day) or current_id(identity, symbol) or f"sym:{norm(symbol)}"

    for day in sorted(other_by_date):
        mine = _ids_on(intervals, identity, day)
        theirs = {theirs_id(s, day): s for s in other_by_date[day]}
        only_primary, only_other = sorted(mine - theirs.keys()), sorted(theirs.keys() - mine)
        result[day] = {"n_primary": len(mine), "n_other": len(theirs),
                       "only_primary_count": len(only_primary), "only_primary": only_primary[:cap],
                       "only_other_count": len(only_other), "only_other": [theirs[i] for i in only_other][:cap]}
    for day in sorted(one_sided or {}):
        mine = _ids_on(intervals, identity, day)
        known = {theirs_id(s, day): s for s in one_sided[day]}
        missing = sorted(known.keys() - mine)
        result[day] = {"n_primary": len(mine), "n_other": len(known), "one_sided": True,
                       "only_other_count": len(missing), "only_other": [known[i] for i in missing][:cap]}
    return dict(sorted(result.items()))


def _write(root, folder: str, doc: dict, identifier: str) -> Path:
    check_dataset_id(identifier)
    target = Path(root) / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{identifier}.json"
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return path


def write_identity(root, doc: dict) -> Path:
    if not isinstance(doc, dict) or set(doc) != set(KEYS) or doc["schema"] != SCHEMA:
        raise ManifestError(f"identity must have schema {SCHEMA} and keys {KEYS}")
    return _write(root, "identity", doc, doc["identity_id"])


def write_coverage(root, doc: dict, coverage_id: str) -> Path:
    if doc.get("schema") != COVERAGE_SCHEMA:
        raise ManifestError(f"coverage must have schema {COVERAGE_SCHEMA}")
    return _write(root, "coverage", doc, coverage_id)


def read_identity(root, identity_id: str) -> dict:
    check_dataset_id(identity_id)
    doc = json.loads((Path(root) / "identity" / f"{identity_id}.json").read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ManifestError(f"{identity_id}: schema is {doc.get('schema')!r}, not {SCHEMA}")
    return doc
