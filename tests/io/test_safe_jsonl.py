"""Unit tests for fscars.io.safe_jsonl."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fscars.io.safe_jsonl import safe_save_jsonl


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _read_rows(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln]


def test_safe_save_creates_file(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    rows = [{"event_id": "a", "x": 1}, {"event_id": "b", "x": 2}]
    n = safe_save_jsonl(out, rows)
    assert n == 2
    assert _read_rows(out) == rows


def test_default_merge_mem_wins_for_shared_keys(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    _write_rows(out, [{"event_id": "a", "x": 1, "extra": "keep"}])

    safe_save_jsonl(out, [{"event_id": "a", "x": 99}])

    rows = _read_rows(out)
    assert len(rows) == 1
    assert rows[0]["x"] == 99
    assert rows[0]["extra"] == "keep"


def test_default_merge_appends_new_rows(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    _write_rows(out, [{"event_id": "a", "x": 1}])

    safe_save_jsonl(out, [{"event_id": "b", "x": 2}])

    rows = sorted(_read_rows(out), key=lambda r: r["event_id"])
    assert rows == [{"event_id": "a", "x": 1}, {"event_id": "b", "x": 2}]


def test_custom_merge_fn(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    _write_rows(out, [{"event_id": "a", "x": 1}])

    def merge(disk, mem):
        return disk + mem

    safe_save_jsonl(out, [{"event_id": "a", "x": 2}], merge_fn=merge)
    rows = _read_rows(out)
    assert len(rows) == 2


def test_concurrent_writes_no_lost_update(tmp_path: Path):
    """Two threads each appending a different event_id keep both rows."""
    out = tmp_path / "opps.jsonl"

    def writer(eid: str, val: int) -> None:
        safe_save_jsonl(out, [{"event_id": eid, "val": val}])

    t1 = threading.Thread(target=writer, args=("a", 1))
    t2 = threading.Thread(target=writer, args=("b", 2))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    rows = {r["event_id"]: r for r in _read_rows(out)}
    assert set(rows) == {"a", "b"}


def test_lock_file_cleaned_up(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    safe_save_jsonl(out, [{"event_id": "a"}])
    assert not (tmp_path / "opps.jsonl.lock").exists()


def test_corrupt_disk_lines_dropped(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    out.write_text('{"event_id": "a"}\nnot json\n{"event_id": "b"}\n', encoding="utf-8")
    safe_save_jsonl(out, [{"event_id": "c"}])
    eids = {r["event_id"] for r in _read_rows(out)}
    assert eids == {"a", "b", "c"}


def test_atomic_write_no_tmp_leftover(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    safe_save_jsonl(out, [{"event_id": "a"}])
    assert not (tmp_path / "opps.jsonl.tmp").exists()


def test_rows_without_key_field_dropped_by_default_merge(tmp_path: Path):
    out = tmp_path / "opps.jsonl"
    safe_save_jsonl(out, [{"event_id": "a"}, {"no_key_here": True}])
    rows = _read_rows(out)
    assert rows == [{"event_id": "a"}]
