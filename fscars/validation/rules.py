"""Capa 4 — deterministic, rule-based opportunity classifier.

A :class:`RulesEngine` maps each ``scar_id`` to a callable that examines
an opportunity row and returns a verdict:

* ``"auto_tp"`` — confident true positive (the scar would correctly fire).
* ``"auto_fp"`` — confident false positive (the opportunity is noise).
* ``"ambiguous"`` — neither rule applies; defer to Capa 3 / human review.

Verdicts are reported as ``(verdict, reason)``. The reason string is kept on
the row so downstream auditing can inspect why a decision was made.

Authors register one classifier per scar via the engine constructor.
Classifiers can be plain functions, lambdas, or any callable matching the
:class:`Classifier` protocol — fscars stays out of the scoring policy itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

Verdict = Literal["auto_tp", "auto_fp", "ambiguous"]

Decision = tuple[Verdict, str]


class Classifier(Protocol):
    """Callable that scores a single opportunity row."""

    def __call__(self, opp: dict[str, Any]) -> Decision: ...


@dataclass
class RulesEngine:
    """Registry of per-scar classifiers, plus a vectorized ``classify_all``.

    Attributes:
        classifiers: Mapping from ``scar_id`` to the classifier callable.
        scar_id_field: Field on each opportunity row that names the scar.
    """

    classifiers: dict[str, Classifier] = field(default_factory=dict)
    scar_id_field: str = "scar_id"

    def register(self, scar_id: str, classifier: Classifier) -> None:
        self.classifiers[scar_id] = classifier

    def classify(self, opp: dict[str, Any]) -> Decision | None:
        """Return ``(verdict, reason)`` or ``None`` if no classifier is registered."""
        scar = opp.get(self.scar_id_field)
        if scar is None:
            return None
        clf = self.classifiers.get(scar)
        if clf is None:
            return None
        return clf(opp)

    def classify_all(
        self,
        opps: list[dict[str, Any]],
        *,
        skip_validated: bool = True,
    ) -> list[Decision | None]:
        """Classify every row. Rows with a non-null ``validated`` are skipped
        by default to avoid re-classifying decided opportunities.
        """
        out: list[Decision | None] = []
        for opp in opps:
            if skip_validated and opp.get("validated") is not None:
                out.append(None)
                continue
            out.append(self.classify(opp))
        return out


def apply_decisions(
    opps: list[dict[str, Any]],
    decisions: list[Decision | None],
    *,
    validated_by: str = "capa_4_auto",
    timestamp: str | None = None,
) -> int:
    """Mutate ``opps`` in place with ``auto_classification*`` and ``validated*``.

    ``auto_tp`` and ``auto_fp`` set ``validated`` to ``True`` / ``False``.
    ``ambiguous`` rows get the metadata but leave ``validated`` untouched so
    Capa 3 (or a human) can still decide.

    Returns the number of rows that received a decision.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    if len(opps) != len(decisions):
        raise ValueError(
            f"opps and decisions length mismatch: {len(opps)} vs {len(decisions)}"
        )
    n = 0
    for opp, dec in zip(opps, decisions, strict=False):
        if dec is None:
            continue
        verdict, reason = dec
        opp["auto_classification"] = verdict
        opp["auto_classification_reason"] = reason
        opp["auto_classified_at"] = timestamp
        if verdict == "auto_tp":
            opp["validated"] = True
            opp["validated_by"] = validated_by
            opp["validated_at"] = timestamp
        elif verdict == "auto_fp":
            opp["validated"] = False
            opp["validated_by"] = validated_by
            opp["validated_at"] = timestamp
        n += 1
    return n


def summarize(
    opps: list[dict[str, Any]],
    decisions: list[Decision | None],
    *,
    scar_id_field: str = "scar_id",
) -> dict[str, dict[str, int]]:
    """Aggregate stats by scar: ``{scar_id: {"auto_tp": N, "auto_fp": N,
    "ambiguous": N, "no_classifier": N, "already_validated": N}}``.
    """
    out: dict[str, dict[str, int]] = {}
    for opp, dec in zip(opps, decisions, strict=False):
        scar = opp.get(scar_id_field, "?")
        bucket = out.setdefault(
            scar,
            {
                "auto_tp": 0,
                "auto_fp": 0,
                "ambiguous": 0,
                "no_classifier": 0,
                "already_validated": 0,
            },
        )
        if dec is None:
            if opp.get("validated") is not None:
                bucket["already_validated"] += 1
            else:
                bucket["no_classifier"] += 1
            continue
        verdict, _ = dec
        bucket[verdict] += 1
    return out


# ---------------------------------------------------------------------------
# Example classifier — illustrates the contract without leaking domain rules.
# ---------------------------------------------------------------------------

_LINE_COUNT_RE = re.compile(r"\b(\d+)L\b")


def line_count_classifier(
    *,
    fp_below: int = 50,
    tp_at_or_above: int = 200,
    notes_field: str = "notes",
) -> Classifier:
    """Build a classifier that uses an embedded line count to decide.

    Expects a ``notes`` string containing ``"<N>L"`` somewhere (e.g.
    ``"code write 122L: foo.py"``). Edits under ``fp_below`` lines are
    treated as trivial (``auto_fp``); edits at or above ``tp_at_or_above``
    are treated as large enough to warrant review (``auto_tp``); everything
    else is ``ambiguous``.

    Returned as a closure so callers can plug it into a :class:`RulesEngine`
    under whichever ``scar_id`` they like.
    """

    def _classify(opp: dict[str, Any]) -> Decision:
        notes = opp.get(notes_field, "")
        m = _LINE_COUNT_RE.search(notes)
        if not m:
            return "ambiguous", "no line count in notes"
        try:
            n = int(m.group(1))
        except ValueError:
            return "ambiguous", "non-integer line count"
        if n < fp_below:
            return "auto_fp", f"trivial edit ({n}L < {fp_below})"
        if n >= tp_at_or_above:
            return "auto_tp", f"large write ({n}L >= {tp_at_or_above})"
        return "ambiguous", f"medium edit ({n}L)"

    return _classify


__all__ = [
    "Classifier",
    "Decision",
    "RulesEngine",
    "Verdict",
    "apply_decisions",
    "line_count_classifier",
    "summarize",
]
