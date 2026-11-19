"""Control-layer readers and checks for the files a registry record points at.

Run manifests, parity receipts and validation receipts are read as plain JSON and
verified by SHA-256; roots are passed in as paths because `research/control` cannot import
the data or evaluation layers. Stdlib only. Every failure raises `RegistryError`.
"""
import hashlib
import json
from pathlib import Path
import re

from research.control.experiment_registry import RegistryError

VALIDATION_SCHEMA = "validation-receipt/v1"
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def safe_segment(value, label):
    """A single path segment: no separators, no `..`, no leading dot."""
    if not isinstance(value, str) or not _SEGMENT.match(value) or ".." in value:
        raise RegistryError(f"{label} {value!r} is not a safe path segment")
    return value


def is_sha256(value):
    return isinstance(value, str) and bool(_SHA.match(value))


def _read_json(path, label, expected_sha):
    path = Path(path)
    if not path.is_file():
        raise RegistryError(f"{label} not found: {path}")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None and sha != expected_sha:
        raise RegistryError(f"{label} sha256 mismatch: file is {sha}, record says {expected_sha}")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise RegistryError(f"{label} is not valid JSON: {path}") from None
    if not isinstance(doc, dict):
        raise RegistryError(f"{label} must be a JSON object: {path}")
    return doc, sha


def read_run_manifest(runs_root, run_id, expected_sha=None):
    """Return `(manifest, sha256)` of `<runs_root>/<run_id>/manifest.json`."""
    safe_segment(run_id, "run_id")
    manifest, sha = _read_json(Path(runs_root) / run_id / "manifest.json", f"run manifest {run_id}", expected_sha)
    if manifest.get("run_id") != run_id:
        raise RegistryError(f"run manifest {run_id} names a different run_id {manifest.get('run_id')!r}")
    return manifest, sha


def read_parity_receipt(parity_root, parity_id, expected_sha=None):
    """Return `(receipt, sha256)` of `<parity_root>/<parity_id>/receipt.json`."""
    safe_segment(parity_id, "parity_id")
    receipt, sha = _read_json(Path(parity_root) / parity_id / "receipt.json", f"parity receipt {parity_id}", expected_sha)
    if receipt.get("parity_id") != parity_id:
        raise RegistryError(f"parity receipt {parity_id} names a different parity_id {receipt.get('parity_id')!r}")
    return receipt, sha


def read_validation_receipt(receipts_dir, receipt_id, expected_sha, run_ids):
    """Read a tracked validation receipt and check the shape Task 4 formalises further.

    Verified here: file exists, sha256 matches, valid JSON, schema, `result == "pass"`,
    and `run_ids` contains every id in `run_ids`.
    """
    safe_segment(receipt_id, "validation receipt id")
    receipt, sha = _read_json(Path(receipts_dir) / f"{receipt_id}.json", f"validation receipt {receipt_id}", expected_sha)
    if receipt.get("schema") != VALIDATION_SCHEMA:
        raise RegistryError(f"validation receipt {receipt_id} is not {VALIDATION_SCHEMA}")
    if receipt.get("result") != "pass":
        raise RegistryError(f"validation receipt {receipt_id} result is {receipt.get('result')!r}, not 'pass'")
    listed = receipt.get("run_ids")
    missing = [r for r in run_ids if not isinstance(listed, list) or r not in listed]
    if missing:
        raise RegistryError(f"validation receipt {receipt_id} does not cover run ids {missing}")
    return receipt, sha


def require_financial_run(manifest):
    """Rule 2: the run is financial use with an accepted-or-passing quality report."""
    run_id = manifest.get("run_id")
    if manifest.get("use") != "financial":
        raise RegistryError(f"run {run_id} is not a financial-use run (use={manifest.get('use')!r}); "
                            "a completed record needs a run made with use: financial")
    datasets = manifest.get("datasets") or {}
    status = datasets.get("quality_status")
    if status == "pass":
        return
    if status == "pass-with-exceptions":
        gate = datasets.get("acceptance")
        if isinstance(gate, dict) and gate.get("status") == "accepted" and is_sha256(gate.get("acceptance_sha256")):
            return
        raise RegistryError(f"run {run_id} used a pass-with-exceptions quality report without a recorded acceptance")
    raise RegistryError(f"run {run_id} quality status {status!r} is neither pass nor accepted pass-with-exceptions")


def require_nautilus_run(manifest):
    if manifest.get("engine") != "nautilus":
        raise RegistryError(f"run {manifest.get('run_id')} engine is {manifest.get('engine')!r}, "
                            "a keep record needs a nautilus run")


def require_passed_parity(receipt, nautilus_run_id):
    """Rule 3: a clean, passing parity receipt for this nautilus run."""
    pid = receipt.get("parity_id")
    if receipt.get("status") != "passed" or receipt.get("passed") is not True:
        raise RegistryError(f"parity receipt {pid} did not pass (status {receipt.get('status')!r})")
    if receipt.get("mismatch_count") != 0:
        raise RegistryError(f"parity receipt {pid} has mismatch_count {receipt.get('mismatch_count')!r}")
    commit = receipt.get("code_commit")
    if not isinstance(commit, str) or not commit or "+dirty" in commit:
        raise RegistryError(f"parity receipt {pid} code_commit {commit!r} is dirty or missing")
    nautilus = ((receipt.get("runs") or {}).get("nautilus") or {}).get("run_id")
    if nautilus != nautilus_run_id:
        raise RegistryError(f"parity receipt {pid} covers nautilus run {nautilus!r}, not {nautilus_run_id!r}")
