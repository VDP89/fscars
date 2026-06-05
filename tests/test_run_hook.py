"""End-to-end test for the run_hook entrypoint."""

from __future__ import annotations

import io
import json
import sys

from fscars import run_hook
from fscars.cli.commands.init import scaffold_scars
from fscars.core.store import default_store


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


def test_run_hook_does_not_fire_in_uninitialized_project(monkeypatch, tmp_path, capsys):
    """Per-project gating: a >200-line write in a project that never ran
    `fscar init` (no `.fscars/scars/`) loads an empty registry, so no scar
    fires even though the file would otherwise trip large-write-review."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {
            "file_path": "demo/big.py",
            "content": "\n".join(f"line_{i}" for i in range(220)),
        },
        "cwd": str(tmp_path),
        "session_id": "test",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.chdir(tmp_path)
    code = run_hook.main([])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out in ("{}", "")


def test_run_hook_fires_after_scaffold(monkeypatch, tmp_path, capsys):
    """Companion to the gating test: once `.fscars/scars/` is scaffolded the
    same oversized Write trips large-write-review (Claude Code shape)."""
    scaffold_scars(default_store(tmp_path))
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {
            "file_path": "demo/big.py",
            "content": "\n".join(f"line_{i}" for i in range(220)),
        },
        "cwd": str(tmp_path),
        "session_id": "test",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.chdir(tmp_path)
    code = run_hook.main([])
    parsed = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "large-write-review" in parsed["hookSpecificOutput"]["additionalContext"]


def test_run_hook_codex_permission_request_denies(monkeypatch, tmp_path, capsys):
    """A project scar targeting PermissionRequest that blocks routes through the
    engine and emits the Codex nested deny decision."""
    scars_dir = default_store(tmp_path).scars_dir
    scars_dir.mkdir(parents=True, exist_ok=True)
    (scars_dir / "deny_rm.py").write_text(
        "from fscars.core.fire import Severity\n"
        "from fscars.core.payload import HookEventType, HookPayload\n"
        "from fscars.core.scar import FunctionalScar, ScarOutput\n"
        "\n"
        "class DenyRm(FunctionalScar):\n"
        "    scar_id = 'deny-rm-rf'\n"
        "    name = 'Deny rm -rf'\n"
        "    rule = 'never rm -rf at the root'\n"
        "    severity = Severity.BLOCK\n"
        "    event_type = HookEventType.PERMISSION_REQUEST\n"
        "    tool_matchers = ('Bash',)\n"
        "    def matches(self, payload: HookPayload) -> bool:\n"
        "        return 'rm -rf' in (payload.content or '')\n"
        "    def build_output(self, payload: HookPayload) -> ScarOutput:\n"
        "        return ScarOutput(additional_context='blocked: rm -rf', block=True)\n"
        "\n"
        "scar = DenyRm()\n",
        encoding="utf-8",
    )
    payload = {
        "hook_event_name": "PermissionRequest",
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(tmp_path),
        "session_id": "t",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.chdir(tmp_path)
    code = run_hook.main(["--adapter", "codex"])
    parsed = json.loads(capsys.readouterr().out)
    # PermissionRequest conveys the deny via JSON only — exit 0, not 2.
    assert code == 0
    decision = parsed["hookSpecificOutput"]["decision"]
    assert decision["behavior"] == "deny"
    assert "rm -rf" in decision["message"]


def test_run_hook_codex_subagent_stop_blocks(monkeypatch, tmp_path, capsys):
    """A SubagentStop scar that blocks emits the top-level decision:block shape
    and exits 2 (a documented SubagentStop block path)."""
    scars_dir = default_store(tmp_path).scars_dir
    scars_dir.mkdir(parents=True, exist_ok=True)
    (scars_dir / "stop_gate.py").write_text(
        "from fscars.core.fire import Severity\n"
        "from fscars.core.payload import HookEventType, HookPayload\n"
        "from fscars.core.scar import FunctionalScar, ScarOutput\n"
        "\n"
        "class CoverageGate(FunctionalScar):\n"
        "    scar_id = 'subagent-coverage-gate'\n"
        "    name = 'Subagent must report coverage'\n"
        "    rule = 'a batch subagent must report coverage before stopping'\n"
        "    severity = Severity.BLOCK\n"
        "    event_type = HookEventType.SUBAGENT_STOP\n"
        "    def matches(self, payload: HookPayload) -> bool:\n"
        "        msg = payload.raw.get('last_assistant_message', '')\n"
        "        return 'coverage' not in msg.lower()\n"
        "    def build_output(self, payload: HookPayload) -> ScarOutput:\n"
        "        return ScarOutput(additional_context='report batch coverage first', block=True)\n"
        "\n"
        "scar = CoverageGate()\n",
        encoding="utf-8",
    )
    payload = {
        "hook_event_name": "SubagentStop",
        "cwd": str(tmp_path),
        "session_id": "t",
        "agent_type": "reviewer",
        "last_assistant_message": "all done",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.chdir(tmp_path)
    code = run_hook.main(["--adapter", "codex"])
    parsed = json.loads(capsys.readouterr().out)
    assert code == 2
    assert parsed["decision"] == "block"
    assert "coverage" in parsed["reason"].lower()


def test_run_hook_codex_apply_patch_emits_native_shape(monkeypatch, tmp_path, capsys):
    """A Codex apply_patch over a >200-line .py file routes through the engine
    (large-write-review fires) and emits the Codex native response shape."""
    scaffold_scars(default_store(tmp_path))  # project must have the scar to fire it
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
    scaffold_scars(default_store(tmp_path))  # project must have the scar to fire it
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
