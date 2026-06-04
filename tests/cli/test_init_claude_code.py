"""Smoke tests for `fscar init --adapter claude_code` (the default adapter).

Mirrors test_init_codex.py so the Claude Code install path is exercised
end-to-end through the CLI across the macOS / Linux / Windows CI matrix.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fscars.adapters.claude_code import ClaudeCodeAdapter
from fscars.cli.main import app

runner = CliRunner()


def _wired_commands(settings_path: Path) -> list[str]:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    return [
        entry.get("command")
        for entries in settings.get("hooks", {}).values()
        for entry in entries
    ]


def test_init_claude_code_wires_settings(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path), "--adapter", "claude_code"])

    assert result.exit_code == 0, result.output
    # The forward-slash descriptor must survive into the message on every OS
    # (regression guard for the Windows pathlib separator bug).
    assert ".claude/settings.json" in result.output
    assert (tmp_path / ".fscars").exists()
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    assert ClaudeCodeAdapter.HOOK_COMMAND in _wired_commands(settings_path)


def test_init_defaults_to_claude_code(tmp_path: Path):
    # No --adapter flag: claude_code is the default, so settings.json is wired.
    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 0, result.output
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    assert ClaudeCodeAdapter.HOOK_COMMAND in _wired_commands(settings_path)


def test_init_scaffolds_starter_scars(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output

    scars_dir = tmp_path / ".fscars" / "scars"
    assert scars_dir.is_dir()
    names = {p.name for p in scars_dir.glob("*.py")}
    expected = {
        "large_write_review.py",
        "utc_timestamps.py",
        "csv_encoding.py",
        "avoid_negative_framing.py",
        "subagent_coverage_report.py",
        "_template.py",
    }
    assert expected <= names
    # The advanced, domain-specific scar is intentionally not scaffolded.
    assert "import_aware_imports.py" not in names


def test_init_does_not_overwrite_edited_scars(tmp_path: Path):
    runner.invoke(app, ["init", str(tmp_path)])
    edited = tmp_path / ".fscars" / "scars" / "large_write_review.py"
    edited.write_text("# my edits\n", encoding="utf-8")

    # Re-running init must leave the user's edits untouched.
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert edited.read_text(encoding="utf-8") == "# my edits\n"


def test_init_no_scars_skips_scaffold(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path), "--no-scars"])
    assert result.exit_code == 0, result.output

    scars_dir = tmp_path / ".fscars" / "scars"
    # No scar files scaffolded; the hook is still wired.
    assert not scars_dir.exists() or not list(scars_dir.glob("*.py"))
    assert (tmp_path / ".claude" / "settings.json").exists()


def test_init_all_scaffolds_advanced_scar(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path), "--all"])
    assert result.exit_code == 0, result.output

    names = {p.name for p in (tmp_path / ".fscars" / "scars").glob("*.py")}
    # `--all` includes the advanced scar omitted from the default set.
    assert "import_aware_imports.py" in names
    assert "large_write_review.py" in names


def test_init_no_scars_and_all_are_mutually_exclusive(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path), "--no-scars", "--all"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
