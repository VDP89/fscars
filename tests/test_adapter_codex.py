"""Unit tests for the Codex native-hooks adapter."""

from __future__ import annotations

import json
from pathlib import Path

from fscars.adapters.codex import CodexAdapter
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import ScarOutput


def _payload(event_type: HookEventType) -> HookPayload:
    return HookPayload(event_type=event_type, session_id="s", cwd="/tmp")


# ----------------------------------------------------------------------
# parse_stdin
# ----------------------------------------------------------------------


def test_parse_pre_tool_use_alias():
    raw = {
        "event": "pre_tool_use",
        "toolName": "Write",
        "toolInput": {"file_path": "src/main.py", "content": "print('hi')"},
        "workspace": "/tmp/p",
        "sessionId": "abc",
    }
    payload = CodexAdapter().parse_stdin(raw)
    assert payload is not None
    assert payload.event_type == HookEventType.PRE_TOOL_USE
    assert payload.tool_name == "Write"
    assert payload.file_path == "src/main.py"
    assert payload.session_id == "abc"


def test_parse_official_bash_payload():
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf build"},
        "session_id": "sess-1",
        "cwd": "/repo",
        "turn_id": "t-9",
        "tool_use_id": "tu-3",
        "permission_mode": "auto",
        "model": "gpt-5-codex",
    }
    payload = CodexAdapter().parse_stdin(raw)
    assert payload is not None
    assert payload.event_type == HookEventType.PRE_TOOL_USE
    assert payload.tool_name == "Bash"
    assert payload.content == "rm -rf build"
    # Non-standard fields are preserved on the raw payload.
    assert payload.raw["turn_id"] == "t-9"
    assert payload.raw["tool_use_id"] == "tu-3"


def test_parse_apply_patch_normalizes_to_edit_and_extracts_path():
    patch = (
        "*** Begin Patch\n"
        "*** Update File: fscars/core/engine.py\n"
        "@@\n"
        "-old\n"
        "+new\n"
        "*** End Patch\n"
    )
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "tool_input": {"command": patch},
        "session_id": "s",
    }
    payload = CodexAdapter().parse_stdin(raw)
    assert payload is not None
    # apply_patch is presented as Edit so Write/Edit-scoped scars still fire.
    assert payload.tool_name == "Edit"
    assert payload.file_path == "fscars/core/engine.py"
    # Original Codex tool name is preserved.
    assert payload.raw["tool_name"] == "apply_patch"


def test_parse_apply_patch_add_file_path():
    patch = "*** Begin Patch\n*** Add File: docs/new.md\n+hello\n*** End Patch\n"
    payload = CodexAdapter().parse_stdin(
        {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": patch}}
    )
    assert payload is not None
    assert payload.file_path == "docs/new.md"


def test_parse_mcp_tool_passes_through():
    payload = CodexAdapter().parse_stdin(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": "/etc/hosts"},
        }
    )
    assert payload is not None
    assert payload.tool_name == "mcp__filesystem__read_file"


def test_parse_unknown_event_returns_none():
    assert CodexAdapter().parse_stdin({"event": "MysteryEvent"}) is None


def test_parse_non_dict_returns_none():
    assert CodexAdapter().parse_stdin(None) is None  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# emit_output — Codex native response schema
# ----------------------------------------------------------------------


def test_emit_pre_tool_use_block_denies():
    out = CodexAdapter().emit_output(
        ScarOutput(additional_context="don't do that", block=True),
        _payload(HookEventType.PRE_TOOL_USE),
    )
    parsed = json.loads(out)
    hso = parsed["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == "don't do that"
    assert "decision" not in parsed


def test_emit_pre_tool_use_context_only():
    out = CodexAdapter().emit_output(
        ScarOutput(additional_context="heads up"),
        _payload(HookEventType.PRE_TOOL_USE),
    )
    parsed = json.loads(out)
    hso = parsed["hookSpecificOutput"]
    assert hso["additionalContext"] == "heads up"
    assert "permissionDecision" not in hso


def test_emit_post_tool_use_block_is_feedback():
    out = CodexAdapter().emit_output(
        ScarOutput(additional_context="too late but note this", block=True),
        _payload(HookEventType.POST_TOOL_USE),
    )
    parsed = json.loads(out)
    assert parsed["decision"] == "block"
    assert parsed["reason"] == "too late but note this"
    assert parsed["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert parsed["hookSpecificOutput"]["additionalContext"] == "too late but note this"


def test_emit_block_without_payload_defaults_to_pre_tool_deny():
    out = CodexAdapter().emit_output(ScarOutput(block=True))
    parsed = json.loads(out)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert parsed["hookSpecificOutput"]["permissionDecisionReason"]


def test_emit_system_message_surfaces_top_level():
    out = CodexAdapter().emit_output(
        ScarOutput(additional_context="ctx", system_message="fscars: 1 scar fired"),
        _payload(HookEventType.USER_PROMPT_SUBMIT),
    )
    parsed = json.loads(out)
    assert parsed["systemMessage"] == "fscars: 1 scar fired"
    assert parsed["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"


def test_emit_empty_output():
    assert CodexAdapter().emit_output(ScarOutput(), _payload(HookEventType.STOP)) == "{}"


# ----------------------------------------------------------------------
# install / hooks.json
# ----------------------------------------------------------------------


def _read_hooks(project: Path) -> dict:
    return json.loads((project / CodexAdapter.HOOKS_FILE).read_text(encoding="utf-8"))


def _fscars_handlers(hooks_config: dict, event: str) -> list[dict]:
    handlers: list[dict] = []
    for group in hooks_config.get("hooks", {}).get(event, []):
        for handler in group.get("hooks", []):
            if "fscars.run_hook" in str(handler.get("command", "")):
                handlers.append(handler)
    return handlers


def test_install_registers_native_hooks(tmp_project: Path):
    CodexAdapter().install(tmp_project)

    config = _read_hooks(tmp_project)
    for event in CodexAdapter.WANTED_EVENTS:
        handlers = _fscars_handlers(config, event)
        assert len(handlers) == 1, event
        handler = handlers[0]
        assert handler["type"] == "command"
        assert handler["command"] == CodexAdapter.HOOK_COMMAND
        assert handler["commandWindows"] == CodexAdapter.HOOK_COMMAND_WINDOWS


def test_install_writes_native_manifest(tmp_project: Path):
    CodexAdapter().install(tmp_project)
    manifest = json.loads(
        (tmp_project / CodexAdapter.MANIFEST_FILE).read_text(encoding="utf-8")
    )
    assert manifest["adapter"] == "codex"
    assert manifest["mode"] == "native-hooks"
    assert manifest["native_hook_status"] == "installed_pending_codex_trust_review"
    assert manifest["hooks_file"] == CodexAdapter.HOOKS_FILE
    assert list(manifest["events"]) == list(CodexAdapter.WANTED_EVENTS)


def test_install_writes_agents_fallback_block(tmp_project: Path):
    CodexAdapter().install(tmp_project)
    agents = (tmp_project / "AGENTS.md").read_text(encoding="utf-8")
    assert CodexAdapter.BLOCK_START in agents
    assert "fscar audit --period 30d" in agents
    assert "/hooks" in agents


def test_install_is_idempotent(tmp_project: Path):
    adapter = CodexAdapter()
    adapter.install(tmp_project)
    adapter.install(tmp_project)

    config = _read_hooks(tmp_project)
    for event in CodexAdapter.WANTED_EVENTS:
        assert len(_fscars_handlers(config, event)) == 1, event

    agents = (tmp_project / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.count(CodexAdapter.BLOCK_START) == 1


def test_install_preserves_foreign_hooks(tmp_project: Path):
    hooks_path = tmp_project / CodexAdapter.HOOKS_FILE
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    foreign = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "/usr/bin/my-linter"}],
                }
            ]
        }
    }
    hooks_path.write_text(json.dumps(foreign), encoding="utf-8")

    CodexAdapter().install(tmp_project)

    config = _read_hooks(tmp_project)
    commands = [
        h.get("command")
        for group in config["hooks"]["PreToolUse"]
        for h in group.get("hooks", [])
    ]
    assert "/usr/bin/my-linter" in commands
    assert CodexAdapter.HOOK_COMMAND in commands


# ----------------------------------------------------------------------
# uninstall
# ----------------------------------------------------------------------


def test_uninstall_removes_fscars_hooks_and_manifest(tmp_project: Path):
    adapter = CodexAdapter()
    adapter.install(tmp_project)
    adapter.uninstall(tmp_project)

    # hooks.json had only fscars entries → file removed.
    assert not (tmp_project / CodexAdapter.HOOKS_FILE).exists()
    assert not (tmp_project / CodexAdapter.MANIFEST_FILE).exists()
    assert not (tmp_project / "AGENTS.md").exists()


def test_uninstall_preserves_foreign_hooks_and_agents(tmp_project: Path):
    agents_path = tmp_project / "AGENTS.md"
    agents_path.write_text("# Repo instructions\n\nKeep this.\n", encoding="utf-8")

    hooks_path = tmp_project / CodexAdapter.HOOKS_FILE
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"hooks": [{"type": "command", "command": "/usr/bin/my-linter"}]}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    adapter = CodexAdapter()
    adapter.install(tmp_project)
    adapter.uninstall(tmp_project)

    config = _read_hooks(tmp_project)
    commands = [
        h.get("command")
        for group in config["hooks"]["PreToolUse"]
        for h in group.get("hooks", [])
    ]
    assert commands == ["/usr/bin/my-linter"]
    assert not _fscars_handlers(config, "PreToolUse")

    agents = agents_path.read_text(encoding="utf-8")
    assert CodexAdapter.BLOCK_START not in agents
    assert "Keep this." in agents
