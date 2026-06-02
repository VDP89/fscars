"""`fscar init` — wire fscars into the current project."""

from __future__ import annotations

from pathlib import Path

import typer

from fscars.adapters.claude_code import ClaudeCodeAdapter
from fscars.adapters.codex import CodexAdapter
from fscars.core.store import default_store


def run(
    path: Path = typer.Argument(
        Path("."),
        help="Project root (defaults to the current directory).",
        file_okay=False,
        resolve_path=True,
    ),
    adapter: str = typer.Option(
        "claude_code",
        "--adapter",
        "-a",
        help="Which AI coding agent to wire up.",
    ),
) -> None:
    """Create .fscars/ and register the hook entrypoint with the chosen adapter."""
    project_root = path
    project_root.mkdir(parents=True, exist_ok=True)

    store = default_store(project_root)
    fresh = not store.exists()
    store.initialize()

    if adapter == "claude_code":
        ClaudeCodeAdapter().install(project_root)
        wired = ".claude/settings.json"
    elif adapter == "codex":
        CodexAdapter().install(project_root)
        wired = "AGENTS.md + .codex/fscars.json"
    else:
        raise typer.BadParameter(f"Unknown adapter: {adapter}")

    if fresh:
        typer.secho(
            f"[OK] Initialized fscars at {store.root}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.echo(f"[OK] fscars already initialized at {store.root}")
    typer.echo(f"[OK] Wired hook entry into {project_root / wired}")
    typer.echo("")
    typer.echo("Next: copy a starter scar from `cookbook/scars/`, or run")
    typer.echo("      `fscar fire <name> \"<rule>\"` to register one inline.")
