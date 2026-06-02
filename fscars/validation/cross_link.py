"""Capa 5 — link opportunity observations to actual hook fires.

The observer captures *opportunities* (potential scar applications) before
the hook decides. The hook itself emits a *fire* when it actually applies.
This module pairs the two so coverage stops being a proxy: an opportunity
with a matching fire is a confirmed hit; an opportunity that was validated
true but has no fire is a confirmed miss.

Match rules:

* same ``scar_id`` and ``session_id``,
* fire timestamp within ``± window_sec`` of opportunity timestamp,
* same filename (if both rows expose one) wins over a bare timestamp match.

When ``dedup=True`` (default), each fire can match at most one opportunity.
Opportunities are processed in chronological order so the earliest opportunity
gets the earliest fire — stable and reproducible.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

MatchMethod = Literal[
    "timestamp+session+filename",
    "timestamp+session",
    "unmatched",
    "no_opp_timestamp",
]


@dataclass
class CrossLinkStats:
    matched: int = 0
    unmatched: int = 0
    opp_no_timestamp: int = 0
    by_scar: dict[str, dict[str, int]] = field(default_factory=dict)


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def normalize_filename(s: str) -> str:
    """Lowercase basename, no surrounding whitespace, path-separator agnostic."""
    if not s:
        return ""
    s = s.replace("\\", "/").strip()
    if "/" in s:
        s = s.rsplit("/", 1)[-1]
    return s.lower().strip()


_TRIGGER_PATH_RE = re.compile(r"/([^/\s]+\.[a-z0-9]+)", re.IGNORECASE)
_TRIGGER_HEAD_RE = re.compile(r"^([\w\-]+\.[a-z0-9]+)", re.IGNORECASE)
_TRIGGER_ANY_RE = re.compile(r"\b([\w\-]+\.[a-z0-9]+)\b", re.IGNORECASE)


def filename_from_trigger(trigger: str) -> str:
    """Best-effort filename extraction from a hook ``trigger_match`` string.

    Hooks log trigger_match in varied formats (``path/to/file.ext``,
    ``script.py — note``, free-text). We try path-like, head, then anywhere.
    Returns ``""`` when no extension-bearing token is found.
    """
    if not trigger:
        return ""
    trigger_norm = trigger.replace("\\", "/")
    for pattern in (_TRIGGER_PATH_RE, _TRIGGER_HEAD_RE, _TRIGGER_ANY_RE):
        m = pattern.search(trigger_norm)
        if m:
            return normalize_filename(m.group(1))
    return ""


def filename_from_notes(notes: str) -> str:
    """Extract the trailing filename from notes shaped like ``label: path``."""
    if not notes or ":" not in notes:
        return ""
    return normalize_filename(notes.split(":", 1)[1])


OppFilenameFn = Callable[[dict[str, Any]], str]
FireFilenameFn = Callable[[dict[str, Any]], str]


def _default_opp_filename(opp: dict[str, Any]) -> str:
    return filename_from_notes(opp.get("notes", ""))


def _default_fire_filename(fire: dict[str, Any]) -> str:
    return filename_from_trigger(fire.get("trigger_match", ""))


def cross_link_fires_opps(
    fires: list[dict[str, Any]],
    opps: list[dict[str, Any]],
    *,
    window_sec: float = 5.0,
    dedup: bool = True,
    scar_id_field: str = "scar_id",
    session_id_field: str = "session_id",
    timestamp_field: str = "timestamp",
    event_id_field: str = "event_id",
    opp_filename_fn: OppFilenameFn = _default_opp_filename,
    fire_filename_fn: FireFilenameFn = _default_fire_filename,
) -> CrossLinkStats:
    """Mutate ``opps`` with ``fire_matched`` / ``fire_event_id`` /
    ``fire_match_method`` / ``fired``. Returns aggregate stats.

    ``fires`` and ``opps`` are not sorted in place; only ``opps`` rows are
    mutated. When ``dedup=True``, each fire's ``event_id`` matches at most
    one opportunity.
    """
    fire_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fire in fires:
        key = (fire.get(scar_id_field, ""), fire.get(session_id_field, ""))
        fire_index[key].append(fire)

    consumed_fire_ids: set[str] = set()
    stats = CrossLinkStats()
    by_scar: dict[str, dict[str, int]] = {}

    opps_sorted = sorted(opps, key=lambda o: o.get(timestamp_field, ""))

    for opp in opps_sorted:
        scar = opp.get(scar_id_field, "")
        session = opp.get(session_id_field, "")
        opp_ts = _parse_ts(opp.get(timestamp_field, ""))
        opp_filename = opp_filename_fn(opp)

        bucket = by_scar.setdefault(scar, {"matched": 0, "unmatched": 0})

        if not opp_ts:
            stats.opp_no_timestamp += 1
            opp["fire_matched"] = False
            opp["fire_match_method"] = "no_opp_timestamp"
            continue

        candidates = fire_index.get((scar, session), [])
        if dedup:
            candidates = [
                c for c in candidates
                if c.get(event_id_field) not in consumed_fire_ids
            ]

        matched_fire = None
        method: MatchMethod = "unmatched"

        for fire in candidates:
            fire_ts = _parse_ts(fire.get(timestamp_field, ""))
            if not fire_ts:
                continue
            if abs((fire_ts - opp_ts).total_seconds()) > window_sec:
                continue
            fire_filename = fire_filename_fn(fire)
            if opp_filename and fire_filename and opp_filename in fire_filename:
                matched_fire = fire
                method = "timestamp+session+filename"
                break
            if matched_fire is None:
                matched_fire = fire
                method = "timestamp+session"

        if matched_fire is not None:
            opp["fire_matched"] = True
            opp["fire_event_id"] = matched_fire.get(event_id_field)
            opp["fire_match_method"] = method
            opp["fired"] = True
            if dedup:
                fire_eid = matched_fire.get(event_id_field)
                if fire_eid is not None:
                    consumed_fire_ids.add(fire_eid)
            stats.matched += 1
            bucket["matched"] += 1
        else:
            opp["fire_matched"] = False
            opp["fire_match_method"] = "unmatched"
            stats.unmatched += 1
            bucket["unmatched"] += 1

    stats.by_scar = by_scar
    return stats


def real_coverage(
    opps: list[dict[str, Any]],
    *,
    scar_id_field: str = "scar_id",
) -> dict[str, dict[str, float | int | None]]:
    """For each scar: ``matched / (matched + missed)`` where ``missed`` are
    opportunities with ``validated=True`` and no fire match. Returns one
    entry per scar with ``matched``, ``missed``, ``coverage`` (None when
    denominator is zero).
    """
    out: dict[str, dict[str, float | int | None]] = {}
    by_scar: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for opp in opps:
        by_scar[opp.get(scar_id_field, "")].append(opp)
    for scar, rows in by_scar.items():
        matched = sum(1 for r in rows if r.get("fire_matched"))
        missed = sum(
            1 for r in rows
            if r.get("validated") is True and not r.get("fire_matched")
        )
        denom = matched + missed
        out[scar] = {
            "matched": matched,
            "missed": missed,
            "coverage": (matched / denom) if denom else None,
        }
    return out


__all__ = [
    "CrossLinkStats",
    "MatchMethod",
    "cross_link_fires_opps",
    "filename_from_notes",
    "filename_from_trigger",
    "normalize_filename",
    "real_coverage",
]
