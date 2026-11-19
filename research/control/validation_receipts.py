"""Validation receipts (`validation-receipt/v1`): the recorded hand-off from researcher to validator.

A `keep` registry record needs a tracked receipt showing a Validation-role skill checked the
runs, and that no researcher skill is the validator. Skill names are self-reported: the tool
enforces separation of recorded roles, not the independence of the model or session that
produced the work. Stdlib only.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

SCHEMA = "validation-receipt/v1"
VALIDATION_SKILLS = ("trade-leakage-audit", "trade-robust-evaluation", "trade-promotion-review")
RESEARCH_SKILLS = ("trade-research-design", "trade-feature-engineering", "trade-experiment",
                   "trade-performance-diagnosis", "trade-candidate-evolution")
KEYS = {"schema", "receipt_id", "created_utc", "run_ids", "parity_receipt_id", "validator",
        "researcher", "checks", "result", "notes"}
CHECK_STATUSES = ("pass", "fail", "waived")
RESULTS = ("pass", "fail")
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class ValidationReceiptError(ValueError):
    pass


def _segment(value, label):
    if not isinstance(value, str) or not _SEGMENT.match(value) or ".." in value:
        raise ValidationReceiptError(f"{label} {value!r} is not a safe path segment")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValidationReceiptError(f"{label} must be non-empty text")
    return value


def _utc(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
    except ValueError:
        stamp = None
    if stamp is None or stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValidationReceiptError(f"created_utc {value!r} is not a UTC ISO timestamp")


def validate_receipt(doc, filename_stem=None):
    """Validate a receipt document; return it. Raises `ValidationReceiptError`."""
    if not isinstance(doc, dict):
        raise ValidationReceiptError("validation receipt must be a JSON object")
    if set(doc) != KEYS:
        raise ValidationReceiptError(
            f"validation receipt keys must be exactly {sorted(KEYS)}; "
            f"missing {sorted(KEYS - set(doc))}, unexpected {sorted(set(doc) - KEYS)}")
    if doc["schema"] != SCHEMA:
        raise ValidationReceiptError(f"schema must be {SCHEMA}, got {doc['schema']!r}")
    receipt_id = _segment(doc["receipt_id"], "receipt_id")
    if filename_stem is not None and receipt_id != filename_stem:
        raise ValidationReceiptError(f"receipt_id {receipt_id!r} must equal the filename stem {filename_stem!r}")
    _utc(doc["created_utc"])
    run_ids = doc["run_ids"]
    if not isinstance(run_ids, list) or not run_ids:
        raise ValidationReceiptError("run_ids must be a non-empty list")
    for run_id in run_ids:
        _segment(run_id, "run_ids entry")
    _segment(doc["parity_receipt_id"], "parity_receipt_id")
    validator, researcher = doc["validator"], doc["researcher"]
    if not isinstance(validator, dict) or set(validator) != {"skill"}:
        raise ValidationReceiptError("validator must be an object with exactly {skill}")
    if not isinstance(researcher, dict) or set(researcher) != {"skills"}:
        raise ValidationReceiptError("researcher must be an object with exactly {skills}")
    skill, skills = validator["skill"], researcher["skills"]
    if skill not in VALIDATION_SKILLS:
        raise ValidationReceiptError(
            f"validator skill {skill!r} is not a Validation skill; allowed: {', '.join(VALIDATION_SKILLS)} "
            f"(Research skills, {', '.join(RESEARCH_SKILLS)}, may not validate their own runs)")
    if not isinstance(skills, list) or not skills:
        raise ValidationReceiptError("researcher.skills must be a non-empty list")
    unknown = [s for s in skills if s not in RESEARCH_SKILLS]
    if unknown:
        raise ValidationReceiptError(
            f"unknown researcher skills {unknown}; allowed: {', '.join(RESEARCH_SKILLS)}")
    checks = doc["checks"]
    if not isinstance(checks, list):
        raise ValidationReceiptError("checks must be a list")
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"name", "status", "detail"}:
            raise ValidationReceiptError("each check must be an object with exactly {name, status, detail}")
        _text(check["name"], "check name")
        if check["status"] not in CHECK_STATUSES:
            raise ValidationReceiptError(f"check {check['name']!r} status must be one of {', '.join(CHECK_STATUSES)}")
        if not isinstance(check["detail"], str):
            raise ValidationReceiptError(f"check {check['name']!r} detail must be text")
    if doc["result"] not in RESULTS:
        raise ValidationReceiptError(f"result must be one of {', '.join(RESULTS)}")
    if not isinstance(doc["notes"], str):
        raise ValidationReceiptError("notes must be text")
    if doc["result"] == "pass":
        if not checks:
            raise ValidationReceiptError("a passing receipt needs at least one check")
        for check in checks:
            if check["status"] == "fail":
                raise ValidationReceiptError(f"a passing receipt cannot contain failed check {check['name']!r}")
            _text(check["detail"], f"detail of check {check['name']!r}")
        if not any(check["status"] == "pass" for check in checks):
            raise ValidationReceiptError("a passing receipt needs at least one check with status 'pass' "
                                         "(waived checks alone are not evidence)")
    return doc


def load_receipt(path):
    """Read and validate a receipt file (the receipt id must equal the file's stem)."""
    path = Path(path)
    if not path.is_file():
        raise ValidationReceiptError(f"validation receipt not found: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise ValidationReceiptError(f"validation receipt is not valid JSON: {path}") from None
    return validate_receipt(doc, path.stem)


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
