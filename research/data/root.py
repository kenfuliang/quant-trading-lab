"""Shared data root: where real-data inputs and run outputs live.

``QTL_DATA_ROOT`` wins. Otherwise the root is ``<main checkout>/data``, so every
git worktree shares one git-ignored data folder. Outside git it is ``<repo root>/data``.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class DataAbsent(RuntimeError):
    """A real-data input is missing; callers print the message and exit 2."""


def _main_checkout(cwd: Path) -> Path | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=cwd,
                             capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    common = Path(out.stdout.strip())
    if not common.is_absolute():
        common = cwd / common
    return Path(os.path.abspath(common)).parent


def data_root(cwd: Path | None = None) -> Path:
    env = os.environ.get("QTL_DATA_ROOT")
    if env:
        return Path(env)
    base = Path(os.path.abspath(cwd if cwd is not None else Path.cwd()))
    main = _main_checkout(base)
    return (main if main is not None else REPO_ROOT) / "data"


def runs_root(cwd: Path | None = None) -> Path:
    return data_root(cwd) / "runs"


def parity_root(cwd: Path | None = None) -> Path:
    return data_root(cwd) / "parity"


def require(path: Path) -> Path:
    if not Path(path).exists():
        raise DataAbsent(f"blocked: data absent: {path}")
    return path
