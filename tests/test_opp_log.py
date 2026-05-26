"""Unit tests for fscars.core.opp_log."""

from __future__ import annotations

from pathlib import Path

from fscars.core.opp_log import log_opportunity, opps_path, read_opps, save_opps


def test_opps_path_layout(tmp_path: Path):
    assert opps_path(tmp_path / ".fscars").parts[-2:] == ("logs", "opportunities.jsonl")


def test_log_opportunity_appends(tmp_path: Path):
    root = tmp_path / ".fscars"
    assert log_opportunity({"event_id": "a", "scar_id": "x"}, root=root)
    assert log_opportunity({"event_id": "b", "scar_id": "y"}, root=root)
    rows = read_opps(root=root)
    assert [r["event_id"] for r in rows] == ["a", "b"]


def test_read_opps_skips_malformed(tmp_path: Path):
    root = tmp_path / ".fscars"
    log_opportunity({"event_id": "a"}, root=root)
    opps_path(root).open("a", encoding="utf-8").write("not json\n")
    log_opportunity({"event_id": "b"}, root=root)
    rows = read_opps(root=root)
    assert [r["event_id"] for r in rows] == ["a", "b"]


def test_save_opps_uses_safe_write(tmp_path: Path):
    root = tmp_path / ".fscars"
    opps = [{"event_id": "a", "x": 1}, {"event_id": "b", "x": 2}]
    n = save_opps(opps, root=root)
    assert n == 2
    rows = read_opps(root=root)
    assert {r["event_id"] for r in rows} == {"a", "b"}
