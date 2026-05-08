"""Unit tests for the Claude Code adapter."""

from __future__ import annotations

import json
from pathlib import Path

from fscars.adapters.claude_code import ClaudeCodeAdapter
from fscars.core.payload import HookEventType
from fscars.core.scar import ScarOutput


def test_parse_pre_tool_use():
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/main.py", "content": "print('hi')"},
        "cwd": "/tmp/p",
        "session_id": "abc",
    }
    payload = ClaudeCodeAdapter().parse_stdin(raw)
    assert payload is not None
    assert payload.event_type == HookEventType.PRE_TOOL_USE
    assert payload.tool_name == "Write"
    assert payload.file_path == "src/main.py"
    assert payload.session_id == "abc"


def test_parse_unknown_event_returns_none():
    payload = ClaudeCodeAdapter().parse_stdin({"hook_event_name": "MysteryEvent"})
    assert payload is None


def test_parse_user_prompt_submit():
    payload = ClaudeCodeAdapter().parse_stdin(
        {"hook_event_name": "UserPromptSubmit", "prompt": "do thing", "cwd": "/tmp/x"}
    )
    assert payload is not None
    assert payload.event_type == HookEventType.USER_PROMPT_SUBMIT
    assert payload.prompt == "do thing"


def test_emit_empty_output_is_compact():
    out = ClaudeCodeAdapter().emit_output(ScarOutput())
    assert out == "{}"


def test_emit_output_with_context_and_block():
    out = ClaudeCodeAdapter().emit_output(
        ScarOutput(
            additional_context="some context",
            system_message="sys",
            block=True,
        )
    )
    parsed = json.loads(out)
    assert parsed["hookSpecificOutput"]["additionalContext"] == "some context"
    assert parsed["hookSpecificOutput"]["decision"] == "block"
    assert parsed["systemMessage"] == "sys"


def test_install_creates_settings(tmp_project: Path):
    adapter = ClaudeCodeAdapter()
    adapter.install(tmp_project)

    settings_path = tmp_project / ".claude" / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = settings["hooks"]
    assert "PreToolUse" in hooks
    assert any(
        item.get("command") == ClaudeCodeAdapter.HOOK_COMMAND
        for item in hooks["PreToolUse"]
    )


def test_install_is_idempotent(tmp_project: Path):
    adapter = ClaudeCodeAdapter()
    adapter.install(tmp_project)
    adapter.install(tmp_project)

    settings = json.loads(
        (tmp_project / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    pre = settings["hooks"]["PreToolUse"]
    matching = [c for c in pre if c.get("command") == ClaudeCodeAdapter.HOOK_COMMAND]
    assert len(matching) == 1


def test_uninstall_removes_only_fscars_entries(tmp_project: Path):
    adapter = ClaudeCodeAdapter()
    settings_path = tmp_project / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"command": "some-other-hook"},
                        {"command": ClaudeCodeAdapter.HOOK_COMMAND},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    adapter.uninstall(tmp_project)
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    pre = settings["hooks"]["PreToolUse"]
    assert pre == [{"command": "some-other-hook"}]
