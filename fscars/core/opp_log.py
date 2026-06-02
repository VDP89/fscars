"""Append-only JSONL opportunities log.

Mirror of :mod:`fscars.core.log` for *opportunities* — candidate scar
applications captured by observers before any hook decides. The validation
pipeline (:mod:`fscars.validation`) consumes these rows.

Reads are tolerant: malformed lines are skipped silently. Writes go through
:func:`fscars.io.safe_jsonl.safe_save_jsonl` so concurrent pipeline scripts
can update fields without losing each other's writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fscars.io.safe_jsonl import safe_save_jsonl


def opps_path(root: Path | None = None) -> Path:
    base = root if root is not None else Path.cwd() / ".fscars"
    return base / "logs" / "opportunities.jsonl"


def log_opportunity(opp: dict[str, Any], *, root: Path | None = None) -> bool:
    """Append a single opportunity dict. Returns True on success.

    Like :func:`fscars.core.log.log_fire`, this is best-effort: a logging
    failure must never break the observer.
    """
    try:
        path = opps_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(opp, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def read_opps(*, root: Path | None = None) -> list[dict[str, Any]]:
    """Read all opportunities from disk. Malformed lines are skipped."""
    path = opps_path(root)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def save_opps(opps: list[dict[str, Any]], *, root: Path | None = None) -> int:
    """Persist opportunities via :func:`safe_save_jsonl`. Returns rows written."""
    path = opps_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    return safe_save_jsonl(path, opps, key_field="event_id")


__all__ = ["log_opportunity", "opps_path", "read_opps", "save_opps"]
