"""Unit tests for the JSONL log."""

from __future__ import annotations

from datetime import datetime, timezone

from fscars.core.fire import Action, FireRecord, Severity
from fscars.core.log import fires_path, log_fire, read_fires
from fscars.core.payload import HookEventType


def _make_record(scar_id: str = "test") -> FireRecord:
    return FireRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_id="abc",
        project_id="def",
        scar_id=scar_id,
        scar_name="Test scar",
        scar_version="1.0.0",
        event_type=HookEventType.PRE_TOOL_USE,
        severity=Severity.WARN,
        action=Action.INJECTED,
    )


def test_fires_path_default(tmp_project):
    path = fires_path(tmp_project / ".fscars")
    assert path.parts[-2:] == ("logs", "fires.jsonl")


def test_log_fire_appends(tmp_project):
    root = tmp_project / ".fscars"
    rec1 = _make_record("a")
    rec2 = _make_record("b")
    assert log_fire(rec1, root=root) is True
    assert log_fire(rec2, root=root) is True

    fires = read_fires(root=root)
    assert [f.scar_id for f in fires] == ["a", "b"]


def test_read_fires_skips_corrupt_lines(tmp_project):
    root = tmp_project / ".fscars"
    log_fire(_make_record("good"), root=root)
    path = fires_path(root)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{ this is not valid json\n")
    log_fire(_make_record("good2"), root=root)

    fires = read_fires(root=root)
    assert [f.scar_id for f in fires] == ["good", "good2"]


def test_log_fire_silent_on_failure(monkeypatch, tmp_project):
    rec = _make_record("x")

    def boom(*a, **kw):
        raise OSError("disk on fire")

    monkeypatch.setattr("fscars.core.log.fires_path", boom)
    assert log_fire(rec, root=tmp_project / ".fscars") is False
