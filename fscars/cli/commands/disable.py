"""`fscar disable` — disable a scar without deleting it."""

from __future__ import annotations

from pathlib import Path

import typer

from fscars.core.store import default_store


def run(
    scar_id: str = typer.Argument(..., help="The scar_id to disable."),
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project root.",
        file_okay=False,
        resolve_path=True,
    ),
    enable: bool = typer.Option(
        False, "--enable", help="Re-enable a previously disabled scar."
    ),
) -> None:
    """Add or remove a scar_id from .fscars/disabled.txt."""
    store = default_store(project)
    if not store.exists():
        typer.secho(
            f"No fscars store at {store.root}. Run `fscar init` first.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    disabled = store.disabled_scars()
    if enable:
        if scar_id not in disabled:
            typer.echo(f"{scar_id} is not currently disabled.")
            return
        disabled.discard(scar_id)
        typer.secho(f"[OK] Re-enabled {scar_id}", fg=typer.colors.GREEN)
    else:
        if scar_id in disabled:
            typer.echo(f"{scar_id} is already disabled.")
            return
        disabled.add(scar_id)
        typer.secho(f"[OK] Disabled {scar_id}", fg=typer.colors.YELLOW)

    lines = sorted(disabled)
    store.disabled_file.write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
