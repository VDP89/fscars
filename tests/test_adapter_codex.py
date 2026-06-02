"""Unit tests for the Codex adapter."""

from __future__ import annotations

import json
from pathlib import Path

from fscars.adapters.codex import CodexAdapter
from fscars.core.payload import HookEventType
from fscars.core.scar import ScarOutput


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


def test_parse_unknown_event_returns_none():
    assert CodexAdapter().parse_stdin({"event": "MysteryEvent"}) is None


def test_emit_output_with_context_and_block():
    out = CodexAdapter().emit_output(
        ScarOutput(
            additional_context="some context",
            system_message="sys",
            block=True,
        )
    )
    parsed = json.loads(out)
    assert parsed["additional_context"] == "some context"
    assert parsed["system_message"] == "sys"
    assert parsed["decision"] == "block"
    assert parsed["block"] is True


def test_install_creates_agents_block_and_manifest(tmp_project: Path):
    adapter = CodexAdapter()
    adapter.install(tmp_project)

    agents = (tmp_project / "AGENTS.md").read_text(encoding="utf-8")
    assert CodexAdapter.BLOCK_START in agents
    assert "fscar audit --period 30d" in agents
    assert CodexAdapter.HOOK_COMMAND in agents

    manifest = json.loads((tmp_project / ".codex" / "fscars.json").read_text(encoding="utf-8"))
    assert manifest["adapter"] == "codex"
    assert manifest["mode"] == "instructions"
    assert manifest["native_hook_status"] == "pending_codex_stable_hook_api"


def test_install_is_idempotent_and_preserves_existing_agents(tmp_project: Path):
    agents_path = tmp_project / "AGENTS.md"
    agents_path.write_text("# Repo instructions\n\nKeep this.\n", encoding="utf-8")

    adapter = CodexAdapter()
    adapter.install(tmp_project)
    adapter.install(tmp_project)

    agents = agents_path.read_text(encoding="utf-8")
    assert agents.count(CodexAdapter.BLOCK_START) == 1
    assert "Keep this." in agents


def test_uninstall_removes_only_fscars_codex_block(tmp_project: Path):
    agents_path = tmp_project / "AGENTS.md"
    agents_path.write_text("# Repo instructions\n\nKeep this.\n", encoding="utf-8")

    adapter = CodexAdapter()
    adapter.install(tmp_project)
    adapter.uninstall(tmp_project)

    agents = agents_path.read_text(encoding="utf-8")
    assert CodexAdapter.BLOCK_START not in agents
    assert "Keep this." in agents
    assert not (tmp_project / ".codex" / "fscars.json").exists()
