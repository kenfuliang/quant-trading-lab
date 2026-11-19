"""Standard per-run output (``run-output/v1``): manifest plus four parquet tables,
written once and hash-verified on read. Runs live under ``.local/runs/<run_id>/``.

Units and dtypes (checked by ``write_run`` and ``read_run``):

- ``date``: string ``YYYY-MM-DD`` (session date) in every table.
- ``instrument``, ``stage``, ``side``: strings; ``side`` is ``BUY`` or ``SELL``.
- ``returns``: ``gross_return``, ``cost`` and ``net_return`` are each a fraction of the
  previous session's equity (``initial_cash`` on the first session), not percent;
  ``net_return = equity / previous equity - 1`` and ``gross_return = net_return + cost``.
  ``equity`` is in USD at the session close.
- ``positions``: ``quantity`` is an integer share count; ``weight`` is position value
  over equity (a fraction).
- ``signals``: ``value`` is a float in the stage's own units.
- ``fills``: ``quantity`` is an integer share count; ``price`` is the fill price in USD
  per share; ``cost`` is the fill's cost in USD (commission plus
  ``|price - open| x quantity``).

Numeric columns must be int or float (not bool); integer columns must be integer
dtype. The manifest's ``config_hash`` must equal ``config_hash(manifest["config"])``.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = "run-output/v1"
COLUMNS: dict[str, tuple[str, ...]] = {
    "returns": ("date", "gross_return", "cost", "net_return", "equity"),
    "positions": ("date", "instrument", "quantity", "weight"),
    "signals": ("date", "instrument", "stage", "value"),
    "fills": ("date", "instrument", "side", "quantity", "price", "cost"),
}
INTEGER_COLUMNS = frozenset({("positions", "quantity"), ("fills", "quantity")})
TEXT_COLUMNS = frozenset({"instrument", "stage", "side"})
DTYPES: dict[str, dict[str, str]] = {
    name: {
        col: "str" if col == "date" or col in TEXT_COLUMNS else "int64" if (name, col) in INTEGER_COLUMNS else "float64"
        for col in cols
    }
    for name, cols in COLUMNS.items()
}
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
MANIFEST_KEYS = (
    "schema", "run_id", "created_utc", "code_commit", "config", "config_hash",
    "engine", "engine_version", "datasets", "coverage", "parent_run",
)


class RunOutputError(ValueError):
    """Raised when a run output is malformed, already exists, or fails verification."""


def config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def new_run_id(config: dict, now: datetime) -> str:
    now = now.astimezone(timezone.utc)
    return f"{now:%Y%m%dT%H%M%SZ}-{config_hash(config)[:8]}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_manifest(manifest: dict) -> None:
    missing = [key for key in MANIFEST_KEYS if key not in manifest]
    if missing:
        raise RunOutputError(f"manifest missing keys: {missing}")
    if manifest["schema"] != SCHEMA:
        raise RunOutputError(f"unsupported schema {manifest['schema']!r}, expected {SCHEMA!r}")
    try:
        expected = config_hash(manifest["config"])
    except TypeError as exc:
        raise RunOutputError(f"manifest config is not JSON-serialisable: {exc}") from exc
    if manifest["config_hash"] != expected:
        raise RunOutputError(f"config_hash {manifest['config_hash']!r} does not match config ({expected})")


def _check_tables(tables: dict[str, pd.DataFrame]) -> None:
    if set(tables) != set(COLUMNS):
        raise RunOutputError(f"tables must be exactly {sorted(COLUMNS)}, got {sorted(tables)}")
    for name, expected in COLUMNS.items():
        if tuple(tables[name].columns) != expected:
            raise RunOutputError(f"{name} columns {tuple(tables[name].columns)} != {expected}")
        for col in expected:
            _check_column(name, col, tables[name][col])


def _check_column(name: str, col: str, series: pd.Series) -> None:
    kind = DTYPES[name][col]
    if kind == "str":
        if not pd.api.types.is_string_dtype(series) or not all(isinstance(v, str) for v in series):
            raise RunOutputError(f"{name}.{col} must be strings, got dtype {series.dtype}")
        if col == "date" and not all(_DATE.fullmatch(v) for v in series):
            raise RunOutputError(f"{name}.date must be YYYY-MM-DD strings")
    elif pd.api.types.is_bool_dtype(series):
        raise RunOutputError(f"{name}.{col} must be numeric, got bool")
    elif kind == "int64" and not pd.api.types.is_integer_dtype(series):
        raise RunOutputError(f"{name}.{col} must be integer dtype, got {series.dtype}")
    elif not pd.api.types.is_numeric_dtype(series):
        raise RunOutputError(f"{name}.{col} must be int or float, got {series.dtype}")


def write_run(root: Path, manifest: dict, tables: dict[str, pd.DataFrame]) -> Path:
    """Write a new immutable run under root/<run_id>; refuses to touch an existing run."""
    manifest = dict(manifest, schema=manifest.get("schema", SCHEMA))
    _check_manifest(manifest)
    _check_tables(tables)
    run_id = str(manifest["run_id"])
    if not run_id or Path(run_id).name != run_id or run_id in (".", ".."):
        raise RunOutputError(f"invalid run_id {run_id!r}")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / run_id
    try:
        path.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise RunOutputError(f"run already exists: {path}") from exc
    files = {}
    for name in COLUMNS:
        target = path / f"{name}.parquet"
        tables[name].to_parquet(target, index=False)
        files[name] = _sha256(target)
    manifest["files"] = files
    (path / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    return path


def read_run(path: Path) -> tuple[dict, dict[str, pd.DataFrame]]:
    """Read a run, verifying schema, manifest keys, config hash, every file hash, table columns and dtypes."""
    path = Path(path)
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise RunOutputError(f"missing manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunOutputError(f"unreadable manifest: {manifest_path}") from exc
    _check_manifest(manifest)
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(COLUMNS):
        raise RunOutputError(f"manifest files must be exactly {sorted(COLUMNS)}")
    tables = {}
    for name in COLUMNS:
        target = path / f"{name}.parquet"
        if not target.is_file():
            raise RunOutputError(f"missing file: {target}")
        if _sha256(target) != files[name]:
            raise RunOutputError(f"hash mismatch: {target}")
        tables[name] = pd.read_parquet(target)
    _check_tables(tables)
    return manifest, tables
