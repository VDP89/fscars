"""Smoke tests for `fscar init --adapter codex` and `fscar doctor --adapter codex`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fscars.adapters.codex import CodexAdapter
from fscars.cli.main import app

runner = CliRunner()


def test_init_codex_wires_native_hooks_and_manifest(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path), "--adapter", "codex"])

    assert result.exit_code == 0, result.output
    assert ".codex/hooks.json" in result.output
    assert "/hooks" in result.output  # trust hint surfaced
    assert (tmp_path / ".fscars").exists()
    assert (tmp_path / CodexAdapter.HOOKS_FILE).exists()
    assert CodexAdapter.BLOCK_START in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert (tmp_path / CodexAdapter.MANIFEST_FILE).exists()


def test_doctor_codex_passes_after_init(tmp_path: Path):
    init = runner.invoke(app, ["init", str(tmp_path), "--adapter", "codex"])
    assert init.exit_code == 0, init.output

    result = runner.invoke(app, ["doctor", "--project", str(tmp_path), "--adapter", "codex"])
    assert result.exit_code == 0, result.output
    assert "Codex native hooks registered" in result.output
    assert "native-hooks mode" in result.output
    assert "[WARN]" not in result.output


def test_doctor_codex_warns_when_hooks_missing(tmp_path: Path):
    # Init for Claude Code, then ask doctor to check the codex wiring.
    runner.invoke(app, ["init", str(tmp_path), "--adapter", "claude_code"])
    result = runner.invoke(app, ["doctor", "--project", str(tmp_path), "--adapter", "codex"])
    # Store exists so no FAIL, but codex wiring is absent → WARN, exit 0.
    assert result.exit_code == 0, result.output
    assert "[WARN]" in result.output
