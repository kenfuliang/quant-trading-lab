#!/usr/bin/env python3
"""Confirm a stored screening run on the NautilusTrader engine.

  confirm.py --run-id ID [--root <data root>] [--runs-root <runs>] [--parity-root <parity>]
             [--allow-dirty]

Reads the screening run ``<runs>/<ID>`` and rebuilds exactly the candidate it records (strategy,
market config, instruments, dataset, and the membership mask when masked). The dataset is
reloaded and its manifest SHA-256 must equal the run's; a membership mask is rebuilt with its
membership and identity hashes verified; a ``use: financial`` run re-verifies the quality gate
from the data root and its acceptance must equal the run's. The core then re-runs the screening
engine (it must reproduce the stored tables exactly), runs NautilusTrader and compares.

Writes the NautilusTrader run (``run-output/v1``, parent = the screening run) and a
``parity-receipt/v1`` receipt ``<parity>/<parity_id>/receipt.json`` (exclusive create), and prints
both ids and the receipt path. Exit 0 only for status ``passed``; 1 for a mismatch (receipt
still written) or a refusal (``error: ...``); 2 for absent data (``blocked: data absent: ...``).
A dirty working tree is refused unless ``--allow-dirty``; such a receipt carries ``+dirty``
and cannot back a ``keep``. Nothing is tuned, and this command never writes the registry, the
trial ledger or an acceptance. Offline and order-free.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.data.manifest import ManifestError  # noqa: E402
from research.data.root import DataAbsent, data_root, parity_root, require, runs_root  # noqa: E402
from research.evaluation.acceptance import AcceptanceError  # noqa: E402
from research.evaluation.confirm import (  # noqa: E402
    ConfirmError, build_receipt, candidate_from_manifest, confirm, native_manifest)
from research.evaluation.datasets import DatasetBlocked, load_dataset  # noqa: E402
from research.evaluation.engine_contract import EngineError  # noqa: E402
from research.evaluation.market_model import MarketDataError  # noqa: E402
from research.evaluation.native_engine import run_native  # noqa: E402
from research.evaluation.run_output import COLUMNS, RunOutputError, new_run_id, read_run, write_run  # noqa: E402
from research.evaluation.strategies import build_target_fn  # noqa: E402
from scripts import analysis  # noqa: E402  (private helpers reused unchanged: _load, _universe, _financial_gate)
from scripts.current import engine_parity  # noqa: E402  (calendar, engine version and exclusive receipt write)

FIXTURE_ID = "synthetic-fixture"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _safe_run_id(value: str) -> str:
    if not value or Path(value).name != value or value in (".", "..") or value.startswith("."):
        raise ConfirmError(f"run id {value!r} is not a single path segment")
    return value


def _load_candidate_data(candidate: dict, root: Path, loader):
    """``(data, provenance)``; the dataset's manifest SHA-256 must equal the stored run's."""
    stored = candidate["datasets"]
    dataset_id = stored.get("dataset_id")
    if dataset_id == FIXTURE_ID and not stored.get("manifest_sha256"):
        spec = {"fixture": True}
    else:
        if not dataset_id or not stored.get("manifest_sha256"):
            raise ConfirmError("the stored run records no dataset id and manifest_sha256; it cannot be confirmed")
        require(root / "manifests" / f"{dataset_id}.json")
        spec = {"dataset_id": dataset_id, "instruments": list(candidate["instruments"])}
    data, provenance = analysis._load(spec, root, loader)
    if spec.get("fixture"):
        return data, provenance
    if provenance.get("manifest_sha256") != stored["manifest_sha256"]:
        raise ConfirmError(f"dataset {dataset_id} manifest_sha256 is {provenance.get('manifest_sha256')}, "
                           f"the screening run recorded {stored['manifest_sha256']}; the data changed")
    return data, provenance


def _reverify_financial(manifest: dict, candidate: dict, root: Path) -> None:
    """Re-verify the quality gate of a financial run; never writes an acceptance."""
    stored = candidate["datasets"]
    relative = stored.get("quality_report")
    if stored.get("dataset_id") == FIXTURE_ID or not relative:
        raise AcceptanceError("a financial run needs a real dataset with a quality report; "
                              "a fixture or unreported dataset is engineering only")
    base = Path(root).resolve()
    resolved = (base / relative).resolve()
    if base not in resolved.parents:
        raise AcceptanceError(f"quality report {relative} is outside the data root")
    gate = analysis._financial_gate({}, root, stored)
    if gate["acceptance_sha256"] != manifest.get("acceptance_sha256"):
        raise ConfirmError(f"the quality gate now gives acceptance_sha256 {gate['acceptance_sha256']}, the screening "
                           f"run recorded {manifest.get('acceptance_sha256')}; the acceptance changed")


def run(args, argv: list[str], loader, native_runner, commit_fn) -> int:
    root, runs, parity = Path(args.root), Path(args.runs_root), Path(args.parity_root)
    commit = commit_fn()
    if commit.endswith("+dirty"):
        if not args.allow_dirty:
            raise ConfirmError("the working tree is dirty, so the code commit does not identify the code; commit "
                               "first, or pass --allow-dirty for an engineering-only confirmation")
        print("warning: dirty tree; this receipt carries +dirty and cannot back a keep", file=sys.stderr)
    run_id = _safe_run_id(args.run_id)
    require(runs / run_id / "manifest.json")
    manifest, tables = read_run(runs / run_id)
    screen_sha = _sha256(runs / run_id / "manifest.json")
    candidate = candidate_from_manifest(manifest)
    data, provenance = _load_candidate_data(candidate, root, loader)
    if manifest.get("use") == "financial":
        _reverify_financial(manifest, candidate, root)
    target_fn = build_target_fn(candidate["strategy"])
    universe_verified = None
    if candidate["universe"]:
        require(root / "membership" / f"{candidate['universe']['membership_id']}.json")
        require(root / "identity" / f"{candidate['universe']['identity_id']}.json")
        wrap, universe_verified = analysis._universe(
            {"membership": candidate["universe"]["membership_id"], "identity": candidate["universe"]["identity_id"]},
            data, root)
        target_fn = wrap(target_fn)
    confirmation = confirm(data, target_fn, candidate["market"], tables, run_native_fn=native_runner)

    now = datetime.now(timezone.utc)
    native = confirmation.native
    n_manifest = native_manifest(manifest, native, code_commit=commit, now=now,
                                 engine_version=engine_parity._engine_version(native.engine))
    n_tables = {name: getattr(native, name)[list(columns)] for name, columns in COLUMNS.items()}
    native_path = write_run(runs, n_manifest, n_tables)
    native_sha = _sha256(native_path / "manifest.json")
    parity_id = new_run_id({"code_commit": commit, "screen_run": run_id, "native_run": n_manifest["run_id"],
                            "kind": "parity"}, now)
    receipt = build_receipt(
        parity_id=parity_id, now=now, command=["scripts/confirm.py", *argv], code_commit=commit,
        screen_manifest=manifest, screen_sha256=screen_sha, native_run_id=n_manifest["run_id"],
        native_sha256=native_sha, confirmation=confirmation, runs_root=str(runs),
        calendar=engine_parity._calendar(data, provenance.get("half_days")))
    if universe_verified is not None:
        receipt["universe_verified"] = universe_verified
    folder = parity / parity_id
    folder.mkdir(parents=True, exist_ok=False)
    engine_parity._write_receipt(folder, receipt)
    print(f"native run: {n_manifest['run_id']}")
    print(f"parity id: {parity_id}")
    print(folder / "receipt.json")
    if receipt["passed"]:
        print("confirmation passed: 0 mismatches")
        return 0
    print(f"confirmation FAILED (status mismatch): {receipt['mismatch_count']} mismatches; first: "
          f"{receipt['mismatches'][:3]}")
    return 1


def main(argv=None, loader=load_dataset, native_runner=run_native, commit_fn=analysis._code_commit) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True, help="the screening run to confirm")
    parser.add_argument("--root", type=Path, default=None, help="data root (default: the shared data root)")
    parser.add_argument("--runs-root", type=Path, default=None, help="run outputs root (default <data root>/runs)")
    parser.add_argument("--parity-root", type=Path, default=None, help="receipts root (default <data root>/parity)")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="confirm from a dirty tree (engineering only; the receipt cannot back a keep)")
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv)
    args.root = args.root if args.root is not None else data_root()
    args.runs_root = args.runs_root if args.runs_root is not None else runs_root()
    args.parity_root = args.parity_root if args.parity_root is not None else parity_root()
    try:
        return run(args, argv, loader, native_runner, commit_fn)
    except DataAbsent as error:
        print(error, file=sys.stderr)
        return 2
    except (ConfirmError, DatasetBlocked, AcceptanceError, ManifestError, MarketDataError, RunOutputError, EngineError,
            OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
