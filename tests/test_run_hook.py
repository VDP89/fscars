"""End-to-end test for the run_hook entrypoint."""

from __future__ import annotations

import io
import json

from fscars import run_hook


def test_run_hook_with_no_input_exits_clean(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    code = run_hook.main([])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "{}"


def test_run_hook_with_unknown_event_emits_empty(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"hook_event_name": "Mystery"})),
    )
    code = run_hook.main([])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "{}"


def test_run_hook_with_pre_tool_use_invokes_engine(monkeypatch, tmp_path, capsys):
    """A real Write event for a small file should not block, but should run."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "demo/main.py", "content": "print('ok')"},
        "cwd": str(tmp_path),
        "session_id": "test",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.chdir(tmp_path)
    code = run_hook.main([])
    captured = capsys.readouterr()
    # No starter scar should fire on a 1-line file — exit 0, empty payload
    assert code == 0
    assert captured.out in ("{}", "")


def test_run_hook_codex_apply_patch_emits_native_shape(monkeypatch, tmp_path, capsys):
    """A Codex apply_patch over a >200-line .py file routes through the engine
    (large-write-review fires) and emits the Codex native response shape."""
    body = "\n".join(f"+line_{i}" for i in range(220))
    patch = f"*** Begin Patch\n*** Update File: demo/big.py\n@@\n{body}\n*** End Patch\n"
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "tool_input": {"command": patch},
        "cwd": str(tmp_path),
        "session_id": "test",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.chdir(tmp_path)
    code = run_hook.main(["--adapter", "codex"])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    # large-write-review is WARN, not block → context injected, exit 0.
    assert code == 0
    assert parsed["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "large-write-review" in parsed["hookSpecificOutput"]["additionalContext"]
