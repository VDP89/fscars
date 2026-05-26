"""Unit tests for fscars.validation.outcome."""

from __future__ import annotations

import pytest

from fscars.validation.outcome import (
    VALID_OUTCOMES,
    OutcomeMarker,
    outcome_stats,
)


def _fire(eid: str, scar: str, **extra) -> dict:
    return {"event_id": eid, "scar_id": scar, **extra}


def test_classify_one_returns_none_without_classifier():
    marker = OutcomeMarker()
    assert marker.classify_one(_fire("e1", "scar_x")) is None


def test_register_and_classify_one():
    marker = OutcomeMarker()
    marker.register("scar_x", lambda f: ("error_prevented", "r"))
    assert marker.classify_one(_fire("e1", "scar_x")) == ("error_prevented", "r")


def test_invalid_outcome_raises():
    marker = OutcomeMarker()
    marker.register("scar_x", lambda f: ("invalid_outcome", "r"))
    with pytest.raises(ValueError):
        marker.classify_one(_fire("e1", "scar_x"))


def test_classify_many_skips_human_marked():
    marker = OutcomeMarker()
    marker.register("scar_x", lambda f: ("error_prevented", "r"))
    fires = [
        _fire("e1", "scar_x"),
        _fire("e2", "scar_x", outcome="false_positive", reviewed_by_human=True),
    ]
    decisions = marker.classify_many(fires)
    assert decisions[0] == ("error_prevented", "r")
    assert decisions[1] is None


def test_classify_many_can_force_through_human_marks():
    marker = OutcomeMarker()
    marker.register("scar_x", lambda f: ("error_prevented", "r"))
    fires = [_fire("e1", "scar_x", outcome="false_positive", reviewed_by_human=True)]
    decisions = marker.classify_many(fires, skip_marked=False)
    assert decisions[0] == ("error_prevented", "r")


def test_apply_mutates_fires():
    marker = OutcomeMarker()
    fires = [_fire("e1", "scar_x")]
    decisions = [("error_prevented", "r")]
    n = marker.apply(fires, decisions, timestamp="t", marker="batch")
    assert n == 1
    assert fires[0]["outcome"] == "error_prevented"
    assert fires[0]["outcome_marked_by"] == "batch"
    assert fires[0]["outcome_reason"] == "r"
    assert fires[0]["outcome_marked_at"] == "t"


def test_apply_skips_none_decisions():
    marker = OutcomeMarker()
    fires = [_fire("e1", "scar_x")]
    n = marker.apply(fires, [None], timestamp="t")
    assert n == 0
    assert "outcome" not in fires[0]


def test_apply_length_mismatch_raises():
    marker = OutcomeMarker()
    with pytest.raises(ValueError):
        marker.apply([_fire("e1", "scar_x")], [], timestamp="t")


def test_mark_manually_sets_human_flag():
    marker = OutcomeMarker()
    fires = [_fire("e1", "scar_x"), _fire("e2", "scar_x")]
    ok = marker.mark_manually(fires, "e2", "error_prevented", timestamp="t")
    assert ok is True
    assert fires[1]["outcome"] == "error_prevented"
    assert fires[1]["reviewed_by_human"] is True
    assert fires[1]["outcome_marked_by"] == "manual"


def test_mark_manually_not_found():
    marker = OutcomeMarker()
    fires = [_fire("e1", "scar_x")]
    assert marker.mark_manually(fires, "missing", "error_prevented") is False


def test_mark_manually_rejects_invalid_outcome():
    marker = OutcomeMarker()
    fires = [_fire("e1", "scar_x")]
    with pytest.raises(ValueError):
        marker.mark_manually(fires, "e1", "bogus")


def test_outcome_stats_aggregation():
    fires = [
        _fire("e1", "scar_x", outcome="error_prevented"),
        _fire("e2", "scar_x", outcome="false_positive"),
        _fire("e3", "scar_x"),  # no outcome → unknown
        _fire("e4", "scar_y", outcome="error_prevented"),
    ]
    stats = outcome_stats(fires)
    assert stats["scar_x"]["error_prevented"] == 1
    assert stats["scar_x"]["false_positive"] == 1
    assert stats["scar_x"]["unknown"] == 1
    assert stats["scar_x"]["total"] == 3
    assert stats["scar_y"]["error_prevented"] == 1


def test_valid_outcomes_contains_required_set():
    assert "error_prevented" in VALID_OUTCOMES
    assert "false_positive" in VALID_OUTCOMES
    assert "unknown" in VALID_OUTCOMES
