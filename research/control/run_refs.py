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
from research.control.validation_receipts import SCHEMA as VALIDATION_SCHEMA, ValidationReceiptError, load_receipt

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


def read_validation_receipt(receipts_dir, receipt_id, expected_sha, run_ids, parity_id=None):
    """Read a tracked validation receipt with the full `validation-receipt/v1` validation.

    Verified: file exists, sha256 matches (when given), the whole shape, the validator
    allowlist and role separation, `result == "pass"`, `run_ids` covers every given id, and
    (when given) `parity_receipt_id` equals `parity_id`.
    """
    safe_segment(receipt_id, "validation receipt id")
    path = Path(receipts_dir) / f"{receipt_id}.json"
    receipt, sha = _read_json(path, f"validation receipt {receipt_id}", expected_sha)
    try:
        load_receipt(path)
    except ValidationReceiptError as error:
        raise RegistryError(f"validation receipt {receipt_id}: {error}") from None
    if receipt.get("result") != "pass":
        raise RegistryError(f"validation receipt {receipt_id} result is {receipt.get('result')!r}, not 'pass'")
    listed = receipt["run_ids"]
    missing = [r for r in run_ids if r not in listed]
    if missing:
        raise RegistryError(f"validation receipt {receipt_id} does not cover run ids {missing}")
    if parity_id is not None and receipt["parity_receipt_id"] != parity_id:
        raise RegistryError(f"validation receipt {receipt_id} covers parity receipt "
                            f"{receipt['parity_receipt_id']!r}, the record names {parity_id!r}")
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


BOUND_CONFIG_KEYS = ("strategy", "market", "instruments")  # the engine differs by design; these must not


def require_nautilus_run(manifest, candidate=None):
    """Rule 3: the NautilusTrader run is a financial-use run (same gate as the candidate run) and,
    when `candidate` (the `refs.run_id` manifest) is given, is bound to it: same dataset hash and the
    same strategy, market and instruments."""
    run_id = manifest.get("run_id")
    if manifest.get("engine") != "nautilus":
        raise RegistryError(f"run {run_id} engine is {manifest.get('engine')!r}, a keep record needs a nautilus run")
    require_financial_run(manifest)
    if candidate is None:
        return
    mine = (manifest.get("datasets") or {}).get("manifest_sha256")
    theirs = (candidate.get("datasets") or {}).get("manifest_sha256")
    if not is_sha256(mine) or mine != theirs:
        raise RegistryError(f"nautilus run {run_id} is not bound to candidate run {candidate.get('run_id')}: "
                            f"dataset manifest_sha256 {mine!r} differs from {theirs!r}")
    config, other = manifest.get("config"), candidate.get("config")
    if not isinstance(config, dict) or not isinstance(other, dict):
        raise RegistryError(f"nautilus run {run_id} or candidate run {candidate.get('run_id')} has no config")
    for key in BOUND_CONFIG_KEYS:
        if key not in config or key not in other or config[key] != other[key]:
            raise RegistryError(f"nautilus run {run_id} is not bound to candidate run {candidate.get('run_id')}: "
                                f"config {key} differs")


def require_passed_parity(receipt):
    """Rule 3: a clean, passing parity receipt. This checks the receipt itself; that it is the
    confirmation of the two cited runs is `require_confirmation`'s job."""
    pid = receipt.get("parity_id")
    if receipt.get("status") != "passed" or receipt.get("passed") is not True:
        raise RegistryError(f"parity receipt {pid} did not pass (status {receipt.get('status')!r})")
    if receipt.get("mismatch_count") != 0:
        raise RegistryError(f"parity receipt {pid} has mismatch_count {receipt.get('mismatch_count')!r}")
    commit = receipt.get("code_commit")
    if not isinstance(commit, str) or not commit or "+dirty" in commit:
        raise RegistryError(f"parity receipt {pid} code_commit {commit!r} is dirty or missing")


def require_confirmation(receipt, run_id, run_sha, nautilus_id, nautilus_sha):
    """Rule 3: the parity receipt is the candidate-confirmation receipt for exactly the two cited
    runs (screening `run_id`/`run_sha`, NautilusTrader `nautilus_id`/`nautilus_sha`), so it vouches
    for the engine code and for these two runs agreeing. A plain engine-parity receipt is refused."""
    pid = receipt.get("parity_id")
    if receipt.get("kind") != "candidate-confirmation":
        raise RegistryError(f"parity receipt {pid} kind is {receipt.get('kind')!r}, a keep needs a "
                            "candidate-confirmation receipt (scripts/confirm.py)")
    runs = receipt.get("runs")
    runs = runs if isinstance(runs, dict) else {}
    for name, want_id, want_sha in (("screen", run_id, run_sha), ("nautilus", nautilus_id, nautilus_sha)):
        got = runs.get(name)
        if got != {"run_id": want_id, "manifest_sha256": want_sha}:
            raise RegistryError(f"parity receipt {pid} runs.{name} is {got!r}, not the cited run {want_id} "
                                f"(manifest sha256 {want_sha}); it does not confirm these runs")
    if receipt.get("stored_screen_identical") is not True:
        raise RegistryError(f"parity receipt {pid} stored_screen_identical is not true")
    if receipt.get("bindable") is not True:
        raise RegistryError(f"parity receipt {pid} is not bindable (no dataset hash binds it)")
