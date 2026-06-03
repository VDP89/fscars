"""End-to-end test for the run_hook entrypoint."""

from __future__ import annotations

import io
import json
import sys

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


def test_run_hook_emits_utf8_even_when_stdout_defaults_to_cp1252(monkeypatch, tmp_path):
    """Regression: a scar message with a non-ASCII char (the em-dash in
    large-write-review) must be written as valid UTF-8 even when stdout
    defaults to cp1252, as it does on a Windows console. Without forcing
    UTF-8, the em-dash is written as byte 0x97 and the host agent (Codex /
    Claude Code) cannot decode the hook output."""
    raw = io.BytesIO()
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(raw, encoding="cp1252", newline=""))

    body = "\n".join(f"+line_{i}" for i in range(220))
    patch = f"*** Begin Patch\n*** Update File: demo/big.py\n@@\n{body}\n*** End Patch\n"
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "tool_input": {"command": patch},
        "cwd": str(tmp_path),
        "session_id": "t",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.chdir(tmp_path)

    run_hook.main(["--adapter", "codex"])
    sys.stdout.flush()
    out_bytes = raw.getvalue()

    out_bytes.decode("utf-8")  # must not raise
    assert b"\xe2\x80\x94" in out_bytes  # UTF-8 em-dash present
    assert b"\x97" not in out_bytes  # not the cp1252 single byte


def test_force_utf8_io_reconfigures_stdin_and_stdout(monkeypatch):
    """Regression (both directions): `_force_utf8_io` must switch stdin and
    stdout to UTF-8 so the host<->hook contract stays UTF-8 regardless of the
    platform default (cp1252 on a Windows console). This covers the input
    direction — a payload with accented text in `tool_input` is read as UTF-8,
    not misread as cp1252 mojibake — as well as the output direction."""
    in_stream = io.TextIOWrapper(io.BytesIO(b"{}"), encoding="cp1252")
    out_stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    assert in_stream.encoding == "cp1252"
    assert out_stream.encoding == "cp1252"

    monkeypatch.setattr("sys.stdin", in_stream)
    monkeypatch.setattr("sys.stdout", out_stream)
    run_hook._force_utf8_io()

    assert in_stream.encoding.replace("-", "").lower() == "utf8"
    assert out_stream.encoding.replace("-", "").lower() == "utf8"
