"""Unit tests for fscars.validation.cross_link."""

from __future__ import annotations

from fscars.validation.cross_link import (
    cross_link_fires_opps,
    filename_from_notes,
    filename_from_trigger,
    normalize_filename,
    real_coverage,
)


def _fire(eid: str, scar: str, ts: str, session: str = "s1", trigger: str = "") -> dict:
    return {
        "event_id": eid,
        "scar_id": scar,
        "timestamp": ts,
        "session_id": session,
        "trigger_match": trigger,
    }


def _opp(eid: str, scar: str, ts: str, session: str = "s1", notes: str = "") -> dict:
    return {
        "event_id": eid,
        "scar_id": scar,
        "timestamp": ts,
        "session_id": session,
        "notes": notes,
    }


def test_normalize_filename_basename_and_lower():
    assert normalize_filename("D:/path/Foo.PY") == "foo.py"
    assert normalize_filename("a\\b\\c.md") == "c.md"
    assert normalize_filename("") == ""


def test_filename_from_notes():
    assert filename_from_notes("entregable text: foo.md") == "foo.md"
    assert filename_from_notes("no colon here") == ""
    assert filename_from_notes("") == ""


def test_filename_from_trigger_variants():
    assert filename_from_trigger("D:/path/file.py") == "file.py"
    assert filename_from_trigger("file.py — note") == "file.py"
    assert filename_from_trigger("inline ref to foo.md among text") == "foo.md"
    assert filename_from_trigger("") == ""
    assert filename_from_trigger("no extension here") == ""


def test_match_within_window():
    fires = [_fire("f1", "x", "2026-05-26T10:00:00+00:00")]
    opps = [_opp("o1", "x", "2026-05-26T10:00:02+00:00")]
    stats = cross_link_fires_opps(fires, opps, window_sec=5)
    assert stats.matched == 1
    assert opps[0]["fire_matched"] is True
    assert opps[0]["fire_event_id"] == "f1"
    assert opps[0]["fired"] is True


def test_unmatched_outside_window():
    fires = [_fire("f1", "x", "2026-05-26T10:00:00+00:00")]
    opps = [_opp("o1", "x", "2026-05-26T10:01:00+00:00")]
    stats = cross_link_fires_opps(fires, opps, window_sec=5)
    assert stats.matched == 0
    assert stats.unmatched == 1
    assert opps[0]["fire_matched"] is False


def test_filename_match_preferred_over_bare_timestamp():
    fires = [
        _fire("f1", "x", "2026-05-26T10:00:01+00:00", trigger="something.txt"),
        _fire("f2", "x", "2026-05-26T10:00:02+00:00", trigger="foo.md note"),
    ]
    opps = [_opp("o1", "x", "2026-05-26T10:00:00+00:00", notes="text: foo.md")]
    cross_link_fires_opps(fires, opps)
    assert opps[0]["fire_event_id"] == "f2"
    assert opps[0]["fire_match_method"] == "timestamp+session+filename"


def test_dedup_consumes_each_fire_once():
    fires = [_fire("f1", "x", "2026-05-26T10:00:00+00:00")]
    opps = [
        _opp("o1", "x", "2026-05-26T10:00:01+00:00"),
        _opp("o2", "x", "2026-05-26T10:00:02+00:00"),
    ]
    stats = cross_link_fires_opps(fires, opps, dedup=True)
    assert stats.matched == 1
    assert stats.unmatched == 1


def test_no_dedup_allows_multiple_matches():
    fires = [_fire("f1", "x", "2026-05-26T10:00:00+00:00")]
    opps = [
        _opp("o1", "x", "2026-05-26T10:00:01+00:00"),
        _opp("o2", "x", "2026-05-26T10:00:02+00:00"),
    ]
    stats = cross_link_fires_opps(fires, opps, dedup=False)
    assert stats.matched == 2


def test_session_mismatch_does_not_match():
    fires = [_fire("f1", "x", "2026-05-26T10:00:00+00:00", session="s1")]
    opps = [_opp("o1", "x", "2026-05-26T10:00:01+00:00", session="s2")]
    stats = cross_link_fires_opps(fires, opps)
    assert stats.matched == 0


def test_opp_without_timestamp():
    fires = [_fire("f1", "x", "2026-05-26T10:00:00+00:00")]
    opps = [{"event_id": "o1", "scar_id": "x", "session_id": "s1"}]
    stats = cross_link_fires_opps(fires, opps)
    assert stats.opp_no_timestamp == 1
    assert opps[0]["fire_match_method"] == "no_opp_timestamp"


def test_real_coverage_computes_ratio():
    opps = [
        {"scar_id": "x", "validated": True, "fire_matched": True},
        {"scar_id": "x", "validated": True, "fire_matched": False},
        {"scar_id": "x", "validated": False, "fire_matched": False},
    ]
    cov = real_coverage(opps)
    assert cov["x"]["matched"] == 1
    assert cov["x"]["missed"] == 1
    assert cov["x"]["coverage"] == 0.5


def test_real_coverage_handles_zero_denominator():
    opps = [{"scar_id": "x", "validated": False, "fire_matched": False}]
    cov = real_coverage(opps)
    assert cov["x"]["coverage"] is None
