"""Lock-guarded, atomic JSONL writes for concurrent observability scripts.

Pipeline scripts (rules classifier, LLM classifier, cross-linker, outcome
marker) all mutate the same opportunities log. Naive load-mutate-save loses
fields when two processes race: each loads the snapshot, mutates its rows
in memory, and the last to write wins, dropping any updates the other
process made.

Strategy (stdlib-only, cross-platform):

1. Acquire an exclusive lock via ``O_CREAT | O_EXCL`` on ``{path}.lock``.
2. Re-load the destination file (it may have been modified while we waited).
3. Merge: caller provides a function that combines on-disk rows with the
   in-memory rows. A field-level default merge keyed by ``event_id`` is
   provided.
4. Atomic write via temp file + ``os.replace``.
5. Release the lock.

Stale locks (older than ``_STALE_LOCK_AGE_SEC``) are auto-broken so a
crashed writer cannot block the pipeline forever.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

_LOCK_TIMEOUT_SEC = 30
_LOCK_POLL_INTERVAL = 0.1
_STALE_LOCK_AGE_SEC = 120

MergeFn = Callable[[list[dict], list[dict]], list[dict]]


def _acquire_lock(lock_path: Path) -> int:
    waited = 0.0
    while waited < _LOCK_TIMEOUT_SEC:
        if lock_path.exists():
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > _STALE_LOCK_AGE_SEC:
                    with contextlib.suppress(OSError):
                        lock_path.unlink()
            except OSError:
                pass

        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except FileExistsError:
            time.sleep(_LOCK_POLL_INTERVAL)
            waited += _LOCK_POLL_INTERVAL
    raise TimeoutError(
        f"Could not acquire lock {lock_path} within {_LOCK_TIMEOUT_SEC}s"
    )


def _release_lock(fd: int, lock_path: Path) -> None:
    with contextlib.suppress(OSError):
        os.close(fd)
    with contextlib.suppress(OSError):
        lock_path.unlink()


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _atomic_write_jsonl(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(str(tmp), str(path))


def _default_merge(
    disk_rows: list[dict],
    mem_rows: list[dict],
    key_field: str = "event_id",
) -> list[dict]:
    """Merge by ``key_field``: in-memory fields win, disk extras preserved."""
    disk_by_key = {r.get(key_field): r for r in disk_rows if r.get(key_field)}
    for mr in mem_rows:
        k = mr.get(key_field)
        if not k:
            continue
        if k in disk_by_key:
            disk_by_key[k].update(mr)
        else:
            disk_by_key[k] = mr
    return list(disk_by_key.values())


def safe_save_jsonl(
    path: Path,
    mem_rows: list[dict],
    *,
    merge_fn: MergeFn | None = None,
    key_field: str = "event_id",
) -> int:
    """Save JSONL with file lock + merge guard against concurrent modifications.

    Args:
        path: Destination JSONL file. Parent directory must exist.
        mem_rows: Rows currently in memory (potentially mutated copies of
            previously loaded rows). Will be merged into the on-disk version.
        merge_fn: Optional custom merge. Receives ``(disk_rows, mem_rows)`` and
            returns the final row set. Defaults to a field-level merge keyed
            by ``key_field`` where in-memory fields win for shared keys and
            disk-only fields are preserved.
        key_field: Field used by the default merge to identify matching rows.

    Returns:
        Number of rows written.

    Raises:
        TimeoutError: If the lock cannot be acquired within 30 seconds.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    fd = _acquire_lock(lock_path)
    try:
        disk_rows = _load_jsonl(path)
        if merge_fn is None:
            merged = _default_merge(disk_rows, mem_rows, key_field=key_field)
        else:
            merged = merge_fn(disk_rows, mem_rows)
        _atomic_write_jsonl(path, merged)
        return len(merged)
    finally:
        _release_lock(fd, lock_path)


__all__ = ["MergeFn", "safe_save_jsonl"]
