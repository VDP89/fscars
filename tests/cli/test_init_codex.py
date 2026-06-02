"""Smoke tests for `fscar init --adapter codex`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fscars.adapters.codex import CodexAdapter
from fscars.cli.main import app

runner = CliRunner()


def test_init_codex_wires_agents_and_manifest(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path), "--adapter", "codex"])

    assert result.exit_code == 0, result.output
    assert "AGENTS.md + .codex/fscars.json" in result.output
    assert (tmp_path / ".fscars").exists()
    assert CodexAdapter.BLOCK_START in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert (tmp_path / ".codex" / "fscars.json").exists()
