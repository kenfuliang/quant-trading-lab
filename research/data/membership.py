"""Point-in-time S&P 500 membership from the fja05680 historical-components CSV.

Each CSV row is ``date,tickers``: the full constituent list in force from that date until the next
row. A symbol's interval runs from the first row that lists it to the last calendar day before the
first later row that does not (``end`` = last day the symbol is a member, ``None`` = still a member).
A symbol that leaves and returns has several intervals. Ticker changes are NOT resolved here:
a renamed company shows as two symbols (see the FB/META spot check; identity is Task 4).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from research.data.calendar import sessions
from research.data.manifest import SCHEMA as MANIFEST_SCHEMA
from research.data.manifest import ManifestError, check_dataset_id, read_manifest, sha256_file

SCHEMA = "membership/v1"
KEYS = ("schema", "membership_id", "created_utc", "source", "intervals", "cross_checks", "spot_checks", "notes")


_DELIST_SUFFIX = re.compile(r"-\d{6}$")
FJA_REPO, HANSHOF_REPO, INDEX_REPO = "fja05680/sp500", "hanshof/sp500_constituents", "unliftedq/index-constitution"
FJA_FILE = "S&P 500 Historical Components & Changes (Updated).csv"


def norm(symbol: str) -> str:
    """Comparison form: upper case, a trailing -YYYYMM delisting suffix (fja05680 style) dropped,
    class-share separator unified to a dot."""
    return _DELIST_SUFFIX.sub("", symbol.strip().upper()).replace("-", ".")


def parse_components(csv_text: str) -> dict:
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader, None)
    if header is None or [h.strip().lower() for h in header] != ["date", "tickers"]:
        raise ValueError(f"expected header date,tickers; got {header!r}")
    rows = []
    for line in reader:
        if not line:
            continue
        if len(line) != 2:
            raise ValueError(f"bad row: {line!r}")
        day = date.fromisoformat(line[0].strip()).isoformat()
        rows.append((day, {s.strip().upper() for s in line[1].split(",") if s.strip()}))
    days = [d for d, _ in rows]
    if len(set(days)) != len(days):
        raise ValueError("duplicate dates in components file")
    rows.sort()
    if not rows:
        raise ValueError("no rows")
    intervals, open_since = {}, {}
    for day, members in rows:
        last_member_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        for symbol in sorted(set(open_since) - members):
            intervals.setdefault(symbol, []).append({"start": open_since.pop(symbol), "end": last_member_day})
        for symbol in sorted(members - set(open_since)):
            open_since[symbol] = day
    for symbol, start in open_since.items():
        intervals.setdefault(symbol, []).append({"start": start, "end": None})
    return {symbol: intervals[symbol] for symbol in sorted(intervals)}


def membership_on(intervals: dict, day: str) -> set:
    """Symbols that are members on ``day`` (that date only; never looks at later rows)."""
    return {symbol for symbol, spans in intervals.items()
            for span in spans if span["start"] <= day and (span["end"] is None or day <= span["end"])}


def cross_check(intervals: dict, other_by_date: dict, cap: int = 25) -> dict:
    """Per date: symmetric difference between this table and another source (names compared by norm())."""
    result = {}
    for day in sorted(other_by_date):
        mine = {norm(s): s for s in membership_on(intervals, day)}
        theirs = {norm(s): s for s in other_by_date[day]}
        only_primary = sorted(mine[k] for k in mine.keys() - theirs.keys())
        only_other = sorted(theirs[k] for k in theirs.keys() - mine.keys())
        result[day] = {"n_primary": len(mine), "n_other": len(theirs),
                       "only_primary_count": len(only_primary), "only_primary": only_primary[:cap],
                       "only_other_count": len(only_other), "only_other": only_other[:cap]}
    return result


def spot_checks(intervals: dict) -> list:
    """Stated expectations; a mismatch is a finding and is never tuned away."""
    def on(symbol, day):
        return symbol in membership_on(intervals, day)

    def throughout(symbol, start, end):
        spans = intervals.get(symbol, [])
        return any(s["start"] <= start and (s["end"] is None or s["end"] >= end) for s in spans)

    tsla_from = on("TSLA", "2020-12-21") and not on("TSLA", "2020-12-18")
    fb = {"FB_on_2022-06-08": on("FB", "2022-06-08"), "META_on_2022-06-09": on("META", "2022-06-09"),
          "FB_on_2022-06-09": on("FB", "2022-06-09"), "META_on_2022-06-08": on("META", "2022-06-08")}
    return [
        {"name": "TSLA member from 2020-12-21", "expected": "member on 2020-12-21, not on 2020-12-18",
         "observed": {"2020-12-18": on("TSLA", "2020-12-18"), "2020-12-21": on("TSLA", "2020-12-21")},
         "result": "pass" if tsla_from else "mismatch"},
        {"name": "AAPL member throughout 2016-01-04..2025-12-31", "expected": "one interval covering the range",
         "observed": intervals.get("AAPL"),
         "result": "pass" if throughout("AAPL", "2016-01-04", "2025-12-31") else "mismatch"},
        {"name": "FB/META ticker change 2022-06-09",
         "expected": "FB present 2022-06-08 and META present 2022-06-09 (either symbol may carry the "
                     "whole history; the ticker change is flagged for Task 4 identity)",
         "observed": fb,
         "result": "pass" if fb["FB_on_2022-06-08"] and fb["META_on_2022-06-09"] else "mismatch"},
        {"name": "members on 2016-01-04", "expected": "about 500-505",
         "observed": len(membership_on(intervals, "2016-01-04")),
         "result": "info"},
        {"name": "members on 2025-12-31", "expected": "about 500-505",
         "observed": len(membership_on(intervals, "2025-12-31")),
         "result": "info"},
    ]


def write_membership(root, doc: dict) -> Path:
    if not isinstance(doc, dict) or set(doc) != set(KEYS):
        raise ManifestError(f"membership keys must be {KEYS}")
    if doc["schema"] != SCHEMA:
        raise ManifestError(f"schema must be {SCHEMA}")
    check_dataset_id(doc["membership_id"])
    folder = Path(root) / "membership"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{doc['membership_id']}.json"
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return path


# --- other sources and the build ----------------------------------------------------------------

def first_trading_days(first_year=2016, last_year=2025) -> list:
    return [sessions(f"{y}-01-01", f"{y}-01-15")[0].strftime("%Y-%m-%d") for y in range(first_year, last_year + 1)]


def parse_current_list(csv_text: str):
    """hanshof: current constituents with 'date added'. Returns (as_of, {symbol: date_added or None})."""
    rows = list(csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"))))
    if not rows or not {"symbol", "date added", "date"} <= set(rows[0]):
        raise ValueError("expected columns symbol, date added, date")
    as_of = {r["date"] for r in rows}
    if len(as_of) != 1:
        raise ValueError(f"expected one as-of date, got {sorted(as_of)}")
    return as_of.pop(), {r["symbol"].strip().upper(): (r["date added"].strip() or None) for r in rows}


def parse_opt_in_out(csv_text: str) -> dict:
    """unliftedq/index-constitution: symbol,name,opt-in,opt-out. opt-out is read as the first day the
    symbol is no longer a member (assumption; a one-day shift only matters on an exit day)."""
    intervals = {}
    for row in csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"))):
        symbol, start, out = row["symbol"].strip().upper(), row["opt-in"].strip(), row["opt-out"].strip()
        if not symbol or not start:
            continue
        end = (date.fromisoformat(out) - timedelta(days=1)).isoformat() if out else None
        intervals.setdefault(symbol, []).append({"start": date.fromisoformat(start).isoformat(), "end": end})
    return intervals


def cross_check_current(intervals: dict, as_of: str, added: dict, days: list, cap: int = 25) -> dict:
    """Current-list source (survivors only). Symmetric difference at ``as_of``; on earlier days only
    the one-sided check: current members already added by that day that this table lacks."""
    result = cross_check(intervals, {as_of: set(added)}, cap)
    for day in days:
        mine = {norm(s) for s in membership_on(intervals, day)}
        expected = sorted(s for s, a in added.items() if a and a <= day and norm(s) not in mine)
        known = [s for s, a in added.items() if a and a <= day]
        result[day] = {"n_primary": len(mine), "n_other": len(known), "one_sided": True,
                       "only_other_count": len(expected), "only_other": expected[:cap]}
    return dict(sorted(result.items()))


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _find(root, snapshot_ids, name):
    """The file called ``name`` in the last snapshot that has it, verified against its manifest."""
    found = None
    for snapshot in snapshot_ids:
        manifest = read_manifest(root, snapshot)
        for entry in manifest["files"]:
            if Path(entry["path"]).name == name:
                found = (entry, manifest)
    return found


def build_from_snapshot(root, snapshot_ids, membership_id, now=None):
    """Build the membership/v1 document from raw GitHub snapshots (later snapshots override earlier
    ones by file name). Returns (doc, inputs, rights)."""
    root = Path(root)
    check_dataset_id(membership_id)
    snapshot_ids = [snapshot_ids] if isinstance(snapshot_ids, str) else list(snapshot_ids)
    primary = _find(root, snapshot_ids, "fja05680-components.csv")
    if primary is None:
        raise ValueError("no fja05680-components.csv in the given snapshots")
    entry, manifest = primary
    data = (root / entry["path"]).read_bytes()
    intervals = parse_components(data.decode("utf-8-sig"))
    inputs = [{"path": entry["path"], "sha256": entry["sha256"]}]
    rights = dict(manifest["rights"])
    licence = _find(root, snapshot_ids, "fja05680-LICENSE")
    if licence:
        inputs.append({"path": licence[0]["path"], "sha256": licence[0]["sha256"]})
        rights["licences"] = {"fja05680-LICENSE": licence[1]["rights"]["licences"]["fja05680-LICENSE"]}
    days = first_trading_days()
    checks = []
    hanshof = _find(root, snapshot_ids, "hanshof-constituents.csv")
    if hanshof is None:
        checks.append({"source": HANSHOF_REPO, "status": "blocked", "reason": "constituent file not fetched"})
    else:
        as_of, added = parse_current_list((root / hanshof[0]["path"]).read_text(encoding="utf-8"))
        inputs.append({"path": hanshof[0]["path"], "sha256": hanshof[0]["sha256"]})
        checks.append({"source": HANSHOF_REPO, "status": "done", "dates": cross_check_current(intervals, as_of, added, days),
                       "reason": f"current list as of {as_of} only (survivors, with date added): one-sided on "
                                 "earlier dates, symmetric on the as-of date"})
    index = _find(root, snapshot_ids, "index-constitution-sp500.csv")
    if index is None:
        checks.append({"source": INDEX_REPO, "status": "blocked",
                       "reason": "no S&P 500 constituent file found via the index-constitution search"})
    else:
        other = parse_opt_in_out((root / index[0]["path"]).read_text(encoding="utf-8"))
        inputs.append({"path": index[0]["path"], "sha256": index[0]["sha256"]})
        checks.append({"source": INDEX_REPO, "status": "done",
                       "dates": cross_check(intervals, {d: membership_on(other, d) for d in days})})
    stamp = now if now is not None else datetime.now(timezone.utc)
    doc = {"schema": SCHEMA, "membership_id": membership_id,
           "created_utc": stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": {"repo": FJA_REPO, "commit_or_file_sha": _git_blob_sha1(data), "file": FJA_FILE,
                      "sha256": entry["sha256"]},
           "intervals": intervals, "cross_checks": checks, "spot_checks": spot_checks(intervals),
           "notes": ("end is the last date the symbol is a member (null = current). fja05680 symbols carry "
                     "a -YYYYMM suffix for names delisted or renamed (kept as given; comparisons drop it). "
                     "Ticker changes are not resolved here (Task 4 identity). "
                     f"Built from snapshots {snapshot_ids}; commit_or_file_sha is the git blob sha1 of the file.")}
    return doc, inputs, rights


def membership_manifest(root, doc, path, inputs, rights) -> dict:
    return {"schema": MANIFEST_SCHEMA, "dataset_id": doc["membership_id"], "kind": "normalised",
            "created_utc": doc["created_utc"], "source": f"{doc['source']['repo']}, per-symbol intervals",
            "inputs": inputs, "recipe": "membership/v1: fja05680 historical components rows to intervals",
            "rights": rights, "files": [{"path": Path(path).relative_to(root).as_posix(), "sha256": sha256_file(path)}],
            "notes": "point-in-time S&P 500 membership; cross_checks and spot_checks are inside the document"}
