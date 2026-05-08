"""Append-only JSONL fires log.

Failures are silent on purpose: nothing here may ever break a hook.
"""

from __future__ import annotations

import json
from pathlib import Path

from fscars.core.fire import FireRecord


def fires_path(root: Path | None = None) -> Path:
    """Return the path to fires.jsonl under the project store."""
    base = root if root is not None else Path.cwd() / ".fscars"
    return base / "logs" / "fires.jsonl"


def log_fire(record: FireRecord, *, root: Path | None = None) -> bool:
    """Append a FireRecord to fires.jsonl. Return True on success.

    All exceptions are swallowed — a logging failure must never break
    the hook execution path.
    """
    try:
        path = fires_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = record.model_dump_json(exclude_none=False)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return True
    except Exception:
        return False


def read_fires(*, root: Path | None = None) -> list[FireRecord]:
    """Read all fires from disk. Used by `fscar log` and `fscar stats`."""
    path = fires_path(root)
    if not path.exists():
        return []
    out: list[FireRecord] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                out.append(FireRecord.model_validate(data))
            except Exception:
                # Skip corrupt lines silently — they are observability data,
                # not source of truth.
                continue
    return out


__all__ = ["fires_path", "log_fire", "read_fires"]
