"""Crash-safe JSON writes and a fail-closed single-writer lock.

Broker-agnostic and offline. A write either leaves the previous complete file or the
new complete file, never a partial one: write a unique temporary file, fsync it,
atomically replace the target, then fsync the directory. An interrupted write leaves
its temporary file behind as evidence; because names are unique it never blocks the
next write. The lock fails closed: a leftover lock after a crash needs a human.
"""
import json
import os
from pathlib import Path
import tempfile

TEMP_PREFIX = ".pending-"


class JournalLockError(RuntimeError):
    pass


def atomic_write_json(path, obj):
    """Durably replace `path` with `obj`; raises before touching it if `obj` is invalid."""
    path = Path(path)
    payload = (json.dumps(obj, indent=2, allow_nan=False) + "\n").encode()
    fd, tmp = tempfile.mkstemp(prefix=TEMP_PREFIX, dir=path.parent)  # O_EXCL, mode 0600
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def leftover_temps(directory):
    """Temporary files from interrupted writes; inspect, never delete automatically."""
    return sorted(Path(directory).glob(TEMP_PREFIX + "*"))


class WriterLock:
    """Exclusive lock file. A collision, including a stale lock, raises and stays put."""

    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise JournalLockError(
                f"Writer lock exists at {self.path}; inspect without deleting evidence."
            ) from None
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        return self

    def __exit__(self, *exc):
        self.path.unlink()
        return False
