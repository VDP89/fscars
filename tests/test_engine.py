"""Unit tests for the dispatch engine."""

from __future__ import annotations

from fscars.core.engine import EngineResult, ScarRegistry, run
from fscars.core.fire import Severity
from fscars.core.payload import HookEventType
from fscars.core.scar import FunctionalScar, ScarOutput


class _NoopWarn(FunctionalScar):
    scar_id = "noop-warn"
    name = "Noop warn"
    rule = "Always fires, warn-only"
    severity = Severity.WARN
    event_type = HookEventType.USER_PROMPT_SUBMIT

    def matches(self, payload):
        return True

    def build_output(self, payload):
        return ScarOutput(additional_context="warn-fragment", system_message="warn")


class _NoopBlock(FunctionalScar):
    scar_id = "noop-block"
    name = "Noop block"
    rule = "Always fires, blocks"
    severity = Severity.BLOCK
    event_type = HookEventType.USER_PROMPT_SUBMIT

    def matches(self, payload):
        return True

    def build_output(self, payload):
        return ScarOutput(additional_context="block-fragment", block=True)


def test_engine_combines_outputs(tmp_project, payload_factory):
    registry = ScarRegistry()
    registry.register(_NoopWarn())
    registry.register(_NoopBlock())

    payload = payload_factory(
        event_type=HookEventType.USER_PROMPT_SUBMIT,
        tool_name=None,
        prompt="anything",
    )

    result = run(payload, registry=registry, log_root=tmp_project / ".fscars")
    assert isinstance(result, EngineResult)
    assert "warn-fragment" in result.output.additional_context
    assert "block-fragment" in result.output.additional_context
    assert result.output.block is True
    assert result.exit_code == 2
    assert sorted(result.matched_scars) == ["noop-block", "noop-warn"]


def test_engine_skips_event_mismatch(tmp_project, payload_factory):
    registry = ScarRegistry()
    registry.register(_NoopWarn())  # registered for UserPromptSubmit

    payload = payload_factory(
        event_type=HookEventType.PRE_TOOL_USE,
        tool_input={"file_path": "x.py"},
    )

    result = run(payload, registry=registry, log_root=tmp_project / ".fscars")
    assert result.matched_scars == []
    assert result.output.is_empty
    assert result.exit_code == 0


def test_engine_swallows_buggy_scar(tmp_project, payload_factory):
    class _Boom(FunctionalScar):
        scar_id = "boom"
        name = "boom"
        rule = "boom"
        severity = Severity.WARN
        event_type = HookEventType.USER_PROMPT_SUBMIT

        def matches(self, payload):
            raise RuntimeError("boom")

        def build_output(self, payload):
            return ScarOutput()

    registry = ScarRegistry()
    registry.register(_Boom())
    registry.register(_NoopWarn())

    payload = payload_factory(
        event_type=HookEventType.USER_PROMPT_SUBMIT,
        tool_name=None,
        prompt="anything",
    )

    result = run(payload, registry=registry, log_root=tmp_project / ".fscars")
    # Buggy scar is skipped, the other still fires.
    assert "boom" not in result.matched_scars
    assert "noop-warn" in result.matched_scars


def test_engine_filters_by_tool_name(tmp_project, payload_factory):
    class _OnlyWrite(FunctionalScar):
        scar_id = "only-write"
        name = "Only Write"
        rule = "Only fires for Write"
        severity = Severity.WARN
        event_type = HookEventType.PRE_TOOL_USE
        tool_matchers = ("Write",)

        def matches(self, payload):
            return True

        def build_output(self, payload):
            return ScarOutput(additional_context="write-only")

    registry = ScarRegistry()
    registry.register(_OnlyWrite())

    matching = payload_factory(tool_name="Write", tool_input={"file_path": "x.py"})
    not_matching = payload_factory(tool_name="Read", tool_input={"file_path": "x.py"})

    r1 = run(matching, registry=registry, log_root=tmp_project / ".fscars")
    r2 = run(not_matching, registry=registry, log_root=tmp_project / ".fscars")

    assert r1.matched_scars == ["only-write"]
    assert r2.matched_scars == []
