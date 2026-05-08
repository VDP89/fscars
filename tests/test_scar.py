"""Unit tests for FunctionalScar base behavior + Scope."""

from __future__ import annotations

from fscars.core.fire import Action, Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput, Scope


class _DummyScar(FunctionalScar):
    scar_id = "dummy"
    name = "Dummy"
    rule = "Dummy rule"
    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Write",)

    def matches(self, payload: HookPayload) -> bool:
        return payload.file_path.endswith(".py")

    def build_output(self, payload: HookPayload) -> ScarOutput:
        return ScarOutput(additional_context="ctx", system_message="sys")


def test_scope_extension_match():
    scope = Scope(extensions=(".py", ".js"))
    assert scope.matches("foo.py")
    assert scope.matches("path/foo.js")
    assert not scope.matches("foo.txt")


def test_scope_path_or_name_match():
    scope = Scope(
        path_fragments=("/marketing/",),
        name_fragments=("brand",),
        extensions=(".md",),
    )
    assert scope.matches("/marketing/copy.md")
    assert scope.matches("/website/brand-page.md")
    assert not scope.matches("/code/main.md")


def test_scope_excludes_block_match():
    scope = Scope(
        extensions=(".md",),
        excludes=("/node_modules/",),
    )
    assert scope.matches("docs/index.md")
    assert not scope.matches("project/node_modules/x.md")


def test_dummy_scar_matches_and_fires(payload_factory):
    scar = _DummyScar()
    payload = payload_factory(tool_input={"file_path": "src/handler.py"})

    assert scar.matches(payload) is True
    output, fire = scar.fire(payload, start_time=None)
    assert output.additional_context == "ctx"
    record = fire.to_record()
    assert record.scar_id == "dummy"
    assert record.action == Action.INJECTED.value
    assert record.tokens_added > 0


def test_scar_blocks_when_output_block_true(payload_factory):
    class BlockingScar(_DummyScar):
        scar_id = "block-test"
        severity = Severity.BLOCK

        def build_output(self, payload):
            return ScarOutput(additional_context="ctx", block=True)

    scar = BlockingScar()
    payload = payload_factory(tool_input={"file_path": "x.py"})
    output, fire = scar.fire(payload)
    assert output.block is True
    record = fire.to_record()
    assert record.action == Action.BLOCKED.value
    assert record.severity == Severity.BLOCK.value


def test_scar_applies_to_event_helper():
    assert _DummyScar.applies_to_event(HookEventType.PRE_TOOL_USE) is True
    assert _DummyScar.applies_to_event(HookEventType.SESSION_START) is False


def test_scar_applies_to_tool_helper():
    assert _DummyScar.applies_to_tool("Write") is True
    assert _DummyScar.applies_to_tool("Read") is False
    assert _DummyScar.applies_to_tool(None) is False
