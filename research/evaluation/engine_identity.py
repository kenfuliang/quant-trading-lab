"""Engine-code identity: which engine source files differ between two commits.

Stdlib only; ``git`` is an injected ``git(args) -> (returncode, stdout)`` callable so the
comparison is testable offline. ``run_git`` is the default runner (local repo, no network).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

ENGINE_FILES = (
    "research/evaluation/engine_contract.py",
    "research/evaluation/screening_engine.py",
    "research/evaluation/native_engine.py",
    "research/evaluation/market_model.py",
    "research/evaluation/parity.py",
    "research/evaluation/run_output.py",
    "requirements.lock.txt",
)

_FULL_SHA = re.compile(r"[0-9a-f]{40}")

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_git(args: list[str]) -> tuple[int, str]:
    done = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return done.returncode, done.stdout


def engine_files_changed(git: Callable[[list[str]], tuple[int, str]], a: str, b: str) -> list[str]:
    """Engine files that differ between commits ``a`` and ``b``; empty means identical."""
    for commit in (a, b):
        if isinstance(commit, str) and commit.endswith("+dirty"):
            raise ValueError(f"{commit}: a dirty commit is not a reproducible engine identity")
        if not isinstance(commit, str) or not _FULL_SHA.fullmatch(commit):
            raise ValueError(f"{commit!r}: engine identity needs a full 40-hex commit SHA "
                             "(not HEAD, a branch, a short SHA or an option)")
    code, out = git(["diff", "--name-only", "--end-of-options", a, b, "--", *ENGINE_FILES])
    if code != 0:
        raise ValueError(f"git diff failed for {a}..{b}: unknown commit ({out.strip()})")
    return [line for line in out.splitlines() if line.strip()]
