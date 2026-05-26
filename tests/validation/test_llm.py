"""Unit tests for fscars.validation.llm — subprocess is fully mocked."""

from __future__ import annotations

from fscars.validation.llm import (
    LLMClassifier,
    LLMVerdict,
    apply_verdict,
)


def _make_classifier(file_content: str | None = "file body", **kwargs) -> LLMClassifier:
    return LLMClassifier(
        scar_descriptions={"scar_x": "test scar"},
        file_resolver=lambda opp: file_content,
        claude_cli="dummy",
        **kwargs,
    )


def test_parse_response_valid_json():
    raw = '{"validated": true, "confidence": 0.9, "reason": "looks right"}'
    parsed = LLMClassifier._parse_response(raw)
    assert parsed is not None
    assert parsed["validated"] is True
    assert parsed["confidence"] == 0.9


def test_parse_response_extracts_json_from_prose():
    raw = 'Here is the answer: {"validated": false, "confidence": 0.3, "reason": "noise"} done.'
    parsed = LLMClassifier._parse_response(raw)
    assert parsed is not None
    assert parsed["validated"] is False


def test_parse_response_empty_or_error():
    assert LLMClassifier._parse_response("") is None
    assert LLMClassifier._parse_response("__ERROR__: boom") is None
    assert LLMClassifier._parse_response("no json here") is None
    assert LLMClassifier._parse_response('{"missing": "keys"}') is None


def test_classify_one_skipped_when_resolver_returns_none():
    clf = _make_classifier(file_content=None)
    verdict = clf.classify_one({"event_id": "e1", "scar_id": "scar_x", "notes": ""})
    assert verdict.status == "skipped_file_not_found"
    assert verdict.event_id == "e1"


def test_classify_one_ok(monkeypatch):
    clf = _make_classifier()

    def fake_call(prompt: str) -> str:
        return '{"validated": true, "confidence": 0.95, "reason": "match"}'

    monkeypatch.setattr(clf, "_call_subprocess", fake_call)
    verdict = clf.classify_one(
        {"event_id": "e1", "scar_id": "scar_x", "notes": "write 100L: foo"}
    )
    assert verdict.status == "ok"
    assert verdict.validated is True
    assert verdict.confidence == 0.95
    assert verdict.reason == "match"


def test_classify_one_parse_fail(monkeypatch):
    clf = _make_classifier()
    monkeypatch.setattr(clf, "_call_subprocess", lambda p: "not json")
    verdict = clf.classify_one({"event_id": "e2", "scar_id": "scar_x", "notes": ""})
    assert verdict.status == "parse_fail"


def test_classify_one_error(monkeypatch):
    clf = _make_classifier()
    monkeypatch.setattr(clf, "_call_subprocess", lambda p: "__ERROR__: kaboom")
    verdict = clf.classify_one({"event_id": "e3", "scar_id": "scar_x", "notes": ""})
    assert verdict.status == "error"


def test_apply_verdict_above_threshold_sets_validated():
    opp: dict = {}
    v = LLMVerdict("e1", "ok", validated=True, confidence=0.9, reason="r")
    wrote = apply_verdict(opp, v, threshold=0.8, timestamp="t", model="haiku")
    assert wrote is True
    assert opp["validated"] is True
    assert opp["validated_by"] == "capa_3_llm_haiku"


def test_apply_verdict_below_threshold_does_not_set_validated():
    opp: dict = {}
    v = LLMVerdict("e1", "ok", validated=True, confidence=0.5, reason="r")
    wrote = apply_verdict(opp, v, threshold=0.8, timestamp="t", model="haiku")
    assert wrote is False
    assert "validated" not in opp
    assert opp["llm_classification"] == "low_confidence"


def test_apply_verdict_skipped_status():
    opp: dict = {}
    v = LLMVerdict("e1", "skipped_file_not_found")
    wrote = apply_verdict(opp, v, threshold=0.8, timestamp="t", model="haiku")
    assert wrote is False
    assert opp["llm_classification"] == "skipped_file_not_found"


def test_apply_verdict_parse_fail():
    opp: dict = {}
    v = LLMVerdict("e1", "parse_fail", raw_response="garbage")
    wrote = apply_verdict(opp, v, threshold=0.8, timestamp="t", model="haiku")
    assert wrote is False
    assert opp["llm_classification"] == "parse_fail"
    assert opp["llm_raw_response"] == "garbage"


def test_classify_many_serial_yields_one_per_opp(monkeypatch):
    clf = _make_classifier(workers=1)
    monkeypatch.setattr(
        clf,
        "_call_subprocess",
        lambda p: '{"validated": true, "confidence": 0.9, "reason": "r"}',
    )
    opps = [
        {"event_id": f"e{i}", "scar_id": "scar_x", "notes": ""} for i in range(3)
    ]
    verdicts = list(clf.classify_many(opps))
    assert len(verdicts) == 3
    assert all(v.status == "ok" for v in verdicts)


def test_classify_many_parallel(monkeypatch):
    clf = _make_classifier(workers=3)
    monkeypatch.setattr(
        clf,
        "_call_subprocess",
        lambda p: '{"validated": false, "confidence": 0.9, "reason": "r"}',
    )
    opps = [
        {"event_id": f"e{i}", "scar_id": "scar_x", "notes": ""} for i in range(5)
    ]
    verdicts = list(clf.classify_many(opps))
    assert len(verdicts) == 5
    assert {v.event_id for v in verdicts} == {f"e{i}" for i in range(5)}


def test_build_prompt_uses_template():
    clf = _make_classifier()
    opp = {
        "scar_id": "scar_x",
        "notes": "write 10L: foo.py",
        "tool_name": "Write",
    }
    prompt = clf.build_prompt(opp, "file content here")
    assert "scar_x" in prompt
    assert "foo.py" in prompt
    assert "Write" in prompt
    assert "file content here" in prompt
    assert "test scar" in prompt  # scar_description interpolated
