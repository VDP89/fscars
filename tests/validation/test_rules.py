"""Unit tests for fscars.validation.rules."""

from __future__ import annotations

import pytest

from fscars.validation.rules import (
    RulesEngine,
    apply_decisions,
    line_count_classifier,
    summarize,
)


def _opp(scar_id: str, notes: str = "", **extra) -> dict:
    return {"scar_id": scar_id, "notes": notes, "event_id": notes or scar_id, **extra}


def test_classify_no_classifier_registered_returns_none():
    engine = RulesEngine()
    assert engine.classify(_opp("scar_foo")) is None


def test_register_and_classify():
    engine = RulesEngine()
    engine.register("scar_x", lambda o: ("auto_tp", "always TP"))
    verdict = engine.classify(_opp("scar_x"))
    assert verdict == ("auto_tp", "always TP")


def test_classify_all_skips_already_validated():
    engine = RulesEngine()
    engine.register("scar_x", lambda o: ("auto_tp", "r"))
    opps = [
        _opp("scar_x"),
        {"scar_id": "scar_x", "validated": True, "notes": ""},
    ]
    decisions = engine.classify_all(opps)
    assert decisions[0] == ("auto_tp", "r")
    assert decisions[1] is None


def test_classify_all_does_not_skip_when_flag_off():
    engine = RulesEngine()
    engine.register("scar_x", lambda o: ("auto_tp", "r"))
    opps = [{"scar_id": "scar_x", "validated": True, "notes": ""}]
    decisions = engine.classify_all(opps, skip_validated=False)
    assert decisions[0] == ("auto_tp", "r")


def test_apply_decisions_sets_validated_for_tp_and_fp():
    opps = [_opp("scar_x"), _opp("scar_y"), _opp("scar_z")]
    decisions = [
        ("auto_tp", "r1"),
        ("auto_fp", "r2"),
        ("ambiguous", "r3"),
    ]
    n = apply_decisions(opps, decisions, timestamp="2026-01-01T00:00:00Z")
    assert n == 3
    assert opps[0]["validated"] is True
    assert opps[1]["validated"] is False
    assert "validated" not in opps[2]
    assert opps[0]["auto_classification"] == "auto_tp"
    assert opps[2]["auto_classification"] == "ambiguous"
    for opp in opps:
        assert opp["auto_classified_at"] == "2026-01-01T00:00:00Z"


def test_apply_decisions_skips_none():
    opps = [_opp("scar_x")]
    n = apply_decisions(opps, [None], timestamp="t")
    assert n == 0
    assert "auto_classification" not in opps[0]


def test_apply_decisions_length_mismatch_raises():
    with pytest.raises(ValueError):
        apply_decisions([_opp("scar_x")], [], timestamp="t")


def test_summarize_counts_per_scar():
    opps = [_opp("scar_x"), _opp("scar_x"), _opp("scar_y")]
    decisions = [("auto_tp", "r"), ("ambiguous", "r"), None]
    stats = summarize(opps, decisions)
    assert stats["scar_x"]["auto_tp"] == 1
    assert stats["scar_x"]["ambiguous"] == 1
    assert stats["scar_y"]["no_classifier"] == 1


def test_summarize_already_validated_bucket():
    opps = [{"scar_id": "scar_x", "validated": True, "notes": ""}]
    stats = summarize(opps, [None])
    assert stats["scar_x"]["already_validated"] == 1


def test_line_count_classifier_thresholds():
    clf = line_count_classifier(fp_below=50, tp_at_or_above=200)
    assert clf({"notes": "write 10L: foo"}) == ("auto_fp", "trivial edit (10L < 50)")
    assert clf({"notes": "write 300L: foo"})[0] == "auto_tp"
    assert clf({"notes": "write 100L: foo"})[0] == "ambiguous"
    assert clf({"notes": "no count here"}) == ("ambiguous", "no line count in notes")


def test_engine_with_custom_scar_id_field():
    engine = RulesEngine(scar_id_field="custom_field")
    engine.register("x", lambda o: ("auto_tp", "r"))
    assert engine.classify({"custom_field": "x"}) == ("auto_tp", "r")
    assert engine.classify({"scar_id": "x"}) is None
