"""``quality-acceptance/v1``: the owner's recorded acceptance of a quality report's exceptions.

An acceptance lives beside the report it covers
(``<root>/quality/<dataset_id>/<stamp>/acceptance.json``), is created exclusively and names the
report by SHA-256, so a changed report invalidates it. Financial use (``verify_for_financial_use``)
needs a ``pass`` report, or a ``pass-with-exceptions`` report whose every non-passing check the
acceptance covers. A ``fail`` report is never usable. Nothing here runs on its own: only the
explicit ``scripts/data.py accept`` command writes an acceptance, and only the owner runs it.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

SCHEMA = "quality-acceptance/v1"
FILE = "acceptance.json"
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class AcceptanceError(ValueError):
    """An acceptance cannot be written, or a report is not usable for financial work."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _segment(value, label: str) -> str:
    if not isinstance(value, str) or not _SEGMENT.match(value) or ".." in value:
        raise AcceptanceError(f"{label} {value!r} is not a safe path segment")
    return value


def uncovered_checks(report: dict) -> list[str]:
    """Names of the checks that did not pass."""
    return [c["name"] for c in report.get("checks", []) if c.get("status") != "pass"]


def write_acceptance(root: Path, dataset_id: str, report_stamp: str, accepted_by: str, accepts: list[str],
                     note: str, now: datetime) -> Path:
    """Record the owner's acceptance of the named report; exclusive create."""
    _segment(dataset_id, "dataset_id")
    _segment(report_stamp, "report_stamp")
    if not isinstance(accepted_by, str) or not accepted_by.strip():
        raise AcceptanceError("accepted_by must be a non-empty name")
    accepts = [a for a in (accepts or []) if isinstance(a, str) and a.strip()]
    if not accepts:
        raise AcceptanceError("accepts must name at least one check, or 'all'")
    folder = Path(root) / "quality" / dataset_id / report_stamp
    report_path = folder / "report.json"
    if not report_path.is_file():
        raise AcceptanceError(f"no quality report {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "pass-with-exceptions":
        raise AcceptanceError(f"report status is {report.get('status')!r}; only a pass-with-exceptions "
                              "report can be accepted")
    if "all" in accepts:
        accepts = ["all"]
    else:
        unknown = sorted(set(accepts) - {c["name"] for c in report["checks"]})
        if unknown:
            raise AcceptanceError(f"unknown checks {unknown}; the report has "
                                  f"{[c['name'] for c in report['checks']]}")
        accepts = sorted(set(accepts))
    doc = {"schema": SCHEMA, "dataset_id": dataset_id, "report_stamp": report_stamp,
           "report_sha256": _sha256(report_path), "accepted_by": accepted_by.strip(),
           "accepted_utc": now.isoformat(), "accepts": accepts, "note": note}
    path = folder / FILE
    with open(path, "x", encoding="utf-8") as stream:  # FileExistsError if already accepted
        stream.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return path


def verify_for_financial_use(root: Path, report_folder: Path, report: dict) -> dict:
    """``{"status": "pass"|"accepted", "acceptance_sha256": str|None}`` or ``AcceptanceError``."""
    folder = Path(report_folder)
    status = report.get("status")
    if status == "pass":
        return {"status": "pass", "acceptance_sha256": None}
    if status != "pass-with-exceptions":
        raise AcceptanceError(f"quality report status {status!r} cannot be used for financial work")
    path = folder / FILE
    needed = uncovered_checks(report)
    if not path.is_file():
        raise AcceptanceError(f"financial use needs an accepted quality report: uncovered checks {needed} "
                              f"(no {FILE} in {folder}); the owner accepts with scripts/data.py accept")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise AcceptanceError(f"malformed acceptance {path}: {error}") from None
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise AcceptanceError(f"{path}: not a {SCHEMA} document")
    report_sha = _sha256(folder / "report.json")
    for field, found, expected in (("dataset_id", doc.get("dataset_id"), report.get("dataset_id")),
                                   ("report_stamp", doc.get("report_stamp"), folder.name),
                                   ("report_sha256", doc.get("report_sha256"), report_sha)):
        if found != expected:
            raise AcceptanceError(f"acceptance {path} does not match this report: {field} {found!r}, "
                                  f"expected {expected!r}")
    if not isinstance(doc.get("accepted_by"), str) or not doc["accepted_by"].strip():
        raise AcceptanceError(f"acceptance {path} has no accepted_by")
    accepts = doc.get("accepts")
    if not isinstance(accepts, list) or not accepts:
        raise AcceptanceError(f"acceptance {path} has no accepts list")
    uncovered = [] if "all" in accepts else [name for name in needed if name not in accepts]
    if uncovered:
        raise AcceptanceError(f"acceptance does not cover checks {uncovered}")
    return {"status": "accepted", "acceptance_sha256": _sha256(path)}
