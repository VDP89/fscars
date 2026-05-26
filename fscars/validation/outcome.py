"""Retroactive outcome marker for hook fires.

Once a hook has fired, its *outcome* is not yet known. Some fires actually
prevented an error; others were noise. This module lets an operator (or a
batch heuristic) annotate each fire with one of five outcomes so coverage
and precision metrics can be computed downstream:

* ``error_prevented`` — fire caught a real error.
* ``false_positive`` — fire was noise; no error existed.
* ``error_repeated`` — hook did not fire and the error happened anyway
  (used when retroactively pairing fires with missed opportunities).
* ``error_despite_fire`` — hook fired but the error still slipped through.
* ``unknown`` — not yet classified.

The :class:`OutcomeMarker` is a registry of per-scar classifiers. Each
classifier is any callable that takes a fire dict and returns
``(outcome, reason)``. fscars does not ship domain heuristics — callers
register their own.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

VALID_OUTCOMES: tuple[str, ...] = (
    "unknown",
    "error_prevented",
    "false_positive",
    "error_repeated",
    "error_despite_fire",
)

OutcomeDecision = tuple[str, str]  # (outcome, reason)
OutcomeClassifier = Callable[[dict], OutcomeDecision]


@dataclass
class OutcomeMarker:
    """Registry of per-scar fire classifiers.

    Attributes:
        classifiers: ``scar_id → callable(fire) → (outcome, reason)``.
        scar_id_field, event_id_field: Field names on the fire dict.
        valid_outcomes: Allowed outcome strings. Callers may extend this
            tuple if their domain needs more granularity.
    """

    classifiers: dict[str, OutcomeClassifier] = field(default_factory=dict)
    scar_id_field: str = "scar_id"
    event_id_field: str = "event_id"
    valid_outcomes: tuple[str, ...] = VALID_OUTCOMES

    def register(self, scar_id: str, classifier: OutcomeClassifier) -> None:
        self.classifiers[scar_id] = classifier

    def classify_one(self, fire: dict) -> OutcomeDecision | None:
        clf = self.classifiers.get(fire.get(self.scar_id_field, ""))
        if clf is None:
            return None
        outcome, reason = clf(fire)
        if outcome not in self.valid_outcomes:
            raise ValueError(
                f"classifier returned invalid outcome {outcome!r}; "
                f"allowed: {self.valid_outcomes}"
            )
        return outcome, reason

    def classify_many(
        self,
        fires: Iterable[dict],
        *,
        skip_marked: bool = True,
    ) -> list[OutcomeDecision | None]:
        """Classify each fire. Fires already marked by a human (``outcome``
        is set, not ``unknown``, and ``reviewed_by_human=True``) are skipped
        when ``skip_marked=True``.
        """
        out: list[OutcomeDecision | None] = []
        for fire in fires:
            if skip_marked and _is_human_marked(fire):
                out.append(None)
                continue
            out.append(self.classify_one(fire))
        return out

    def apply(
        self,
        fires: list[dict],
        decisions: list[OutcomeDecision | None],
        *,
        marker: str = "auto_classify_rules",
        timestamp: str | None = None,
    ) -> int:
        """Mutate ``fires`` with outcome metadata. Returns rows updated."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        if len(fires) != len(decisions):
            raise ValueError(
                f"fires and decisions length mismatch: "
                f"{len(fires)} vs {len(decisions)}"
            )
        n = 0
        for fire, dec in zip(fires, decisions, strict=False):
            if dec is None:
                continue
            outcome, reason = dec
            fire["outcome"] = outcome
            fire["outcome_marked_at"] = timestamp
            fire["outcome_marked_by"] = marker
            fire["outcome_reason"] = reason
            n += 1
        return n

    def mark_manually(
        self,
        fires: list[dict],
        event_id: str,
        outcome: str,
        *,
        timestamp: str | None = None,
    ) -> bool:
        """Set ``outcome`` on the matching fire. Returns True if found.

        Manual marks set ``reviewed_by_human=True`` so subsequent batch
        classify_many calls skip them by default.
        """
        if outcome not in self.valid_outcomes:
            raise ValueError(
                f"outcome must be one of {self.valid_outcomes}, got {outcome!r}"
            )
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        for fire in fires:
            if fire.get(self.event_id_field) == event_id:
                fire["outcome"] = outcome
                fire["outcome_marked_at"] = timestamp
                fire["outcome_marked_by"] = "manual"
                fire["reviewed_by_human"] = True
                return True
        return False


def _is_human_marked(fire: dict) -> bool:
    outcome = fire.get("outcome")
    return (
        bool(outcome)
        and outcome != "unknown"
        and bool(fire.get("reviewed_by_human"))
    )


def outcome_stats(
    fires: list[dict],
    *,
    scar_id_field: str = "scar_id",
) -> dict[str, dict[str, int]]:
    """Aggregate ``{scar_id: {outcome: count, ..., "total": N}}``. Fires
    without an explicit ``outcome`` field count as ``"unknown"``.
    """
    out: dict[str, dict[str, int]] = {}
    for fire in fires:
        scar = fire.get(scar_id_field, "?")
        outcome = fire.get("outcome") or "unknown"
        bucket = out.setdefault(scar, Counter())
        bucket[outcome] += 1
        bucket["total"] += 1
    return {scar: dict(counter) for scar, counter in out.items()}


__all__ = [
    "VALID_OUTCOMES",
    "OutcomeClassifier",
    "OutcomeDecision",
    "OutcomeMarker",
    "outcome_stats",
]
