"""Dataset loader: a verified, quality-gated ``MarketData`` from a normalised manifest.

``load_dataset`` reads and verifies the ``dataset-manifest/v1`` (every input hash), refuses
a dataset with no quality report or whose latest report is ``fail``, re-applies the
``etf-normalise/v1`` recipe to the full rows and returns the requested instruments plus
provenance. Lives under ``research/evaluation`` because it consumes ``normalise``.
"""
from __future__ import annotations

import json
from pathlib import Path

from research.data.manifest import ManifestError, read_manifest, sha256_file
from research.data.root import data_root, require
from research.evaluation.etf_normalise import RECIPE, normalise
from research.evaluation.market_model import MarketData


LOADABLE_STATUSES = ("pass", "pass-with-exceptions")


class DatasetBlocked(RuntimeError):
    """The dataset has no quality report, or its latest report failed."""


def _latest_folder(root: Path, dataset_id: str) -> Path | None:
    base = Path(root) / "quality" / dataset_id
    if not base.is_dir():
        return None
    folders = sorted(p for p in base.iterdir() if (p / "report.json").is_file())
    return folders[-1] if folders else None


def latest_report(root: Path, dataset_id: str) -> dict | None:
    """The newest quality report (by its UTC timestamp folder), or None."""
    folder = _latest_folder(root, dataset_id)
    if folder is None:
        return None
    return json.loads((folder / "report.json").read_text(encoding="utf-8"))


def load_dataset(dataset_id: str, instruments: tuple[str, ...],
                 root: Path | None = None) -> tuple[MarketData, dict]:
    base = Path(root) if root is not None else data_root()
    manifest = read_manifest(base, dataset_id, verify=True)
    if manifest["kind"] != "normalised" or len(manifest["inputs"]) != 2:
        raise ManifestError(f"{dataset_id}: not a normalised dataset with bars and actions inputs")
    if manifest["recipe"] != RECIPE:
        raise ManifestError(f"{dataset_id}: unsupported recipe {manifest['recipe']}")
    folder = _latest_folder(base, dataset_id)
    if folder is None:
        raise DatasetBlocked(f"{dataset_id}: no quality report; run scripts/data.py quality first")
    path = folder / "report.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise DatasetBlocked(f"{dataset_id}: malformed quality report {path}: {error}") from None
    if not isinstance(report, dict):
        raise DatasetBlocked(f"{dataset_id}: malformed quality report {path}: not a JSON object")
    manifest_sha = sha256_file(base / "manifests" / f"{dataset_id}.json")
    inputs = report.get("inputs")
    recorded = inputs.get("manifest_sha256") if isinstance(inputs, dict) else None
    for field, found, expected in (("dataset_id", report.get("dataset_id"), dataset_id),
                                   ("recipe", report.get("recipe"), RECIPE),
                                   ("inputs.manifest_sha256", recorded, manifest_sha)):
        if found != expected:
            raise DatasetBlocked(f"{dataset_id}: latest quality report {path} has {field} {found!r}, "
                                 f"expected {expected!r}; rerun scripts/data.py quality")
    status = report.get("status")
    if status not in LOADABLE_STATUSES:
        raise DatasetBlocked(f"{dataset_id}: latest quality report status {status!r} is not loadable ({path})")
    bars_path, actions_path = (require(base / entry["path"]) for entry in manifest["inputs"])
    rows = json.loads(bars_path.read_text(encoding="utf-8"))
    actions = json.loads(actions_path.read_text(encoding="utf-8"))
    # The in-kind value is computed from the full rows, so a converted event survives
    # when its child instrument is not requested.
    result = normalise(rows, actions, tuple(instruments))
    provenance = {
        "manifest_sha256": manifest_sha,
        "quality_status": status,
        "acceptance": report.get("acceptance"),
        "quality_report": (folder / "report.json").relative_to(base).as_posix(),
        "inputs": [dict(entry) for entry in manifest["inputs"]],
        "half_days": [item["session"] for check in report["checks"] if check["name"] == "half_days"
                      for item in check["items"]],
    }
    return result.data, provenance
