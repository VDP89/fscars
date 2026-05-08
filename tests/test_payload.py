"""Unit tests for HookPayload."""

from __future__ import annotations

from fscars.core.payload import HookEventType, HookPayload


def test_payload_lowercases_path(payload_factory):
    p = payload_factory(tool_input={"file_path": "C:\\Users\\X\\Foo.PY"})
    assert p.file_path == "c:/users/x/foo.py"


def test_payload_content_collapses_keys(payload_factory):
    p = payload_factory(tool_input={"new_string": "abc"})
    assert p.content == "abc"

    p = payload_factory(tool_input={"content": "xyz"})
    assert p.content == "xyz"

    p = payload_factory(tool_input={})
    assert p.content == ""


def test_payload_line_count(payload_factory):
    p = payload_factory(tool_input={"content": "a\nb\nc"})
    assert p.line_count == 3

    p = payload_factory(tool_input={"content": ""})
    assert p.line_count == 0


def test_payload_event_type_enum():
    p = HookPayload(event_type=HookEventType.SESSION_START)
    assert p.event_type == HookEventType.SESSION_START
