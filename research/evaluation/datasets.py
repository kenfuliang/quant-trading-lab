"""Dataset loader: a verified, quality-gated ``MarketData`` from a normalised manifest.

``load_dataset`` reads and verifies the ``dataset-manifest/v1`` (every input hash), refuses
a dataset with no quality report or whose latest report is ``fail``, re-applies the
``etf-normalise/v1`` recipe to the full rows and returns the requested instruments plus
provenance. Lives under ``research/evaluation`` because it consumes ``normalise``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from research.data.manifest import ManifestError, read_manifest, sha256_file
from research.data.root import data_root, require
from research.evaluation.etf_normalise import RECIPE, normalise
from research.evaluation.market_model import BAR_COLUMNS, Dividend, MarketData, MarketDataError, Split


LOADABLE_STATUSES = ("pass", "pass-with-exceptions")
CACHE_SCHEMA = "normalised-cache/v1"
CACHE_MANIFEST = "cache-manifest.json"
ACTIONS_FILE = "corporate-actions.json"


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


def read_inputs(base: Path, manifest: dict) -> tuple[list[dict], dict]:
    """Rows of every bar input plus the actions file (always the last input)."""
    if manifest["kind"] != "normalised" or len(manifest["inputs"]) < 2:
        raise ManifestError(f"{manifest['dataset_id']}: not a normalised dataset with bars and actions inputs")
    *bar_entries, actions_entry = manifest["inputs"]
    rows: list[dict] = []
    for entry in bar_entries:
        rows.extend(json.loads(require(base / entry["path"]).read_text(encoding="utf-8")))
    actions = json.loads(require(base / actions_entry["path"]).read_text(encoding="utf-8"))
    return rows, actions


def _write_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _write_cache(folder: Path, manifest_sha: str, data: MarketData) -> None:
    """Parquet per frame plus the actions and a manifest of file hashes (derived data, atomic writes)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / CACHE_MANIFEST).unlink(missing_ok=True)
    files = []
    for name, frame in data.bars.items():
        path = folder / f"bars-{name}.parquet"
        frame.reset_index(drop=True).to_parquet(path.with_name(path.name + ".tmp"), engine="pyarrow",
                                                index=False)
        os.replace(path.with_name(path.name + ".tmp"), path)
        files.append({"path": path.name, "sha256": sha256_file(path)})
    actions = {"sessions": list(data.sessions),
               "dividends": [[d.instrument, d.ex_date, d.pay_date, d.per_share] for d in data.dividends],
               "splits": [[s.instrument, s.effective_date, s.ratio] for s in data.splits]}
    path = folder / ACTIONS_FILE
    _write_atomic(path, json.dumps(actions, sort_keys=True).encode("utf-8"))
    files.append({"path": path.name, "sha256": sha256_file(path)})
    info = {"schema": CACHE_SCHEMA, "manifest_sha256": manifest_sha, "recipe": RECIPE,
            "symbols": sorted(data.bars), "files": files}
    _write_atomic(folder / CACHE_MANIFEST, (json.dumps(info, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _read_cache(folder: Path, manifest_sha: str) -> MarketData | None:
    """The cached full-universe ``MarketData`` if every hash verifies, else None (never trusted)."""
    try:
        info = json.loads((folder / CACHE_MANIFEST).read_text(encoding="utf-8"))
        if (info["schema"], info["manifest_sha256"], info["recipe"]) != (CACHE_SCHEMA, manifest_sha, RECIPE):
            return None
        paths = {}
        for entry in info["files"]:
            relative = Path(entry["path"])
            if relative.name != entry["path"]:
                return None
            target = folder / relative
            if not target.is_file() or sha256_file(target) != entry["sha256"]:
                return None
            paths[entry["path"]] = target
        if set(paths) != {f"bars-{s}.parquet" for s in info["symbols"]} | {ACTIONS_FILE}:
            return None
        actions = json.loads(paths[ACTIONS_FILE].read_text(encoding="utf-8"))
        sessions = tuple(actions["sessions"])
        index = pd.Index(sessions, name="date")
        bars = {}
        for symbol in info["symbols"]:
            frame = pd.read_parquet(paths[f"bars-{symbol}.parquet"], engine="pyarrow")
            if list(frame.columns) != list(BAR_COLUMNS) or len(frame) != len(sessions):
                return None
            frame.index = index
            bars[symbol] = frame
        return MarketData(sessions=sessions, bars=bars,
                          dividends=tuple(Dividend(*item) for item in actions["dividends"]),
                          splits=tuple(Split(*item) for item in actions["splits"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _restrict(data: MarketData, instruments: tuple[str, ...]) -> MarketData:
    names = tuple(instruments)
    if not names or len(set(names)) != len(names):
        raise MarketDataError(f"instruments must be non-empty and unique, got {names}")
    missing = [n for n in names if n not in data.bars]
    if missing:
        raise MarketDataError(f"no bars for instruments {missing}")
    wanted = set(names)
    return MarketData(sessions=data.sessions, bars={n: data.bars[n] for n in names},
                      dividends=tuple(d for d in data.dividends if d.instrument in wanted),
                      splits=tuple(s for s in data.splits if s.instrument in wanted))


def load_dataset(dataset_id: str, instruments: tuple[str, ...],
                 root: Path | None = None) -> tuple[MarketData, dict]:
    base = Path(root) if root is not None else data_root()
    manifest = read_manifest(base, dataset_id, verify=True)
    if manifest["kind"] != "normalised" or len(manifest["inputs"]) < 2:
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
    cache_state = None
    if len(manifest["inputs"]) > 2:
        # Stock layer: many per-symbol files. The normalised result is cached per manifest hash
        # and only trusted after every cache file verifies; otherwise it is rebuilt.
        cache = base / "cache" / manifest_sha
        data = _read_cache(cache, manifest_sha)
        cache_state = "hit"
        if data is None:
            rows, actions = read_inputs(base, manifest)
            data = normalise(rows, actions, tuple(sorted({row["symbol"] for row in rows}))).data
            cache_state = "rebuilt"
            try:
                _write_cache(cache, manifest_sha, data)
            except OSError:
                cache_state = "uncached"
        market = _restrict(data, tuple(instruments))
    else:
        rows, actions = read_inputs(base, manifest)
        # The in-kind value is computed from the full rows, so a converted event survives
        # when its child instrument is not requested.
        market = normalise(rows, actions, tuple(instruments)).data
    provenance = {
        "manifest_sha256": manifest_sha,
        "quality_status": status,
        "acceptance": report.get("acceptance"),
        "quality_report": (folder / "report.json").relative_to(base).as_posix(),
        "inputs": [dict(entry) for entry in manifest["inputs"]],
        "universe_kind": manifest.get("universe_kind"),
        "half_days": [item["session"] for check in report["checks"] if check["name"] == "half_days"
                      for item in check["items"]],
    }
    if cache_state is not None:
        provenance["cache"] = cache_state
    return market, provenance
