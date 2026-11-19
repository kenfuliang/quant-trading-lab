"""Dataset manifests: what a dataset is, where it came from and the hashes of its files.

A manifest is written once (exclusive create) under ``<root>/manifests/<dataset_id>.json``.
Paths inside it are relative to the data root.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = "dataset-manifest/v1"
KINDS = ("raw-snapshot", "normalised")
KEYS = ("schema", "dataset_id", "kind", "created_utc", "source", "inputs", "recipe", "rights", "files", "notes")
OPTIONAL_KEYS = ("universe_kind",)


class ManifestError(ValueError):
    """A manifest is malformed, or a file it names is missing or changed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_dataset_id(dataset_id) -> None:
    if not isinstance(dataset_id, str) or not dataset_id or "/" in dataset_id or dataset_id.startswith("."):
        raise ManifestError("dataset_id must be a plain name")


def _validate(manifest: dict) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be an object")
    missing = [k for k in KEYS if k not in manifest]
    extra = [k for k in manifest if k not in KEYS and k not in OPTIONAL_KEYS]
    if missing or extra:
        raise ManifestError(f"manifest keys: missing {missing}, unexpected {extra}")
    if manifest["schema"] != SCHEMA:
        raise ManifestError(f"schema must be {SCHEMA}")
    if manifest["kind"] not in KINDS:
        raise ManifestError(f"kind must be one of {KINDS}")
    check_dataset_id(manifest["dataset_id"])
    if "universe_kind" in manifest and (not isinstance(manifest["universe_kind"], str)
                                        or not manifest["universe_kind"]):
        raise ManifestError("universe_kind must be a non-empty string")
    for key in ("inputs", "files"):
        if not isinstance(manifest[key], list) or any(
                not isinstance(e, dict) or set(e) != {"path", "sha256"} for e in manifest[key]):
            raise ManifestError(f"{key} must be a list of {{path, sha256}}")


def write_manifest(root: Path, manifest: dict) -> Path:
    _validate(manifest)
    folder = Path(root) / "manifests"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{manifest['dataset_id']}.json"
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_manifest(root: Path, dataset_id: str, verify: bool = True) -> dict:
    path = Path(root) / "manifests" / f"{dataset_id}.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ManifestError(f"{path}: unreadable: {error}") from None
    _validate(manifest)
    if manifest["dataset_id"] != dataset_id:
        raise ManifestError(f"{path}: dataset_id mismatch")
    entries = manifest["inputs"] + manifest["files"]
    for entry in entries:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ManifestError(f"{entry['path']}: path must be relative to the data root")
    if verify:
        for entry in entries:
            target = Path(root) / entry["path"]
            if not target.is_file():
                raise ManifestError(f"{entry['path']}: missing")
            if sha256_file(target) != entry["sha256"]:
                raise ManifestError(f"{entry['path']}: sha256 mismatch")
    return manifest
