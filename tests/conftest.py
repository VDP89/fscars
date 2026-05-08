"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from fscars.core.payload import HookEventType, HookPayload


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A fresh project root with no fscars config."""
    return tmp_path


def make_payload(
    *,
    event_type: HookEventType = HookEventType.PRE_TOOL_USE,
    tool_name: str | None = "Write",
    tool_input: dict | None = None,
    prompt: str | None = None,
    cwd: str = "/tmp/test",
) -> HookPayload:
    return HookPayload(
        event_type=event_type,
        tool_name=tool_name,
        tool_input=tool_input or {},
        prompt=prompt,
        cwd=cwd,
        session_id="test-session",
        raw={},
    )


@pytest.fixture
def payload_factory():
    return make_payload
