"""`fscar` Typer application — top-level CLI."""

from __future__ import annotations

import typer

from fscars import __version__
from fscars.cli.commands import (
    audit,
    dashboard,
    disable,
    doctor,
    init,
    list_cmd,
    log_cmd,
    stats,
    validate,
)

app = typer.Typer(
    name="fscar",
    help="Functional Scars - bolt-on correction primitive for AI coding agents.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.command("init", help="Wire fscars into the current project.")(init.run)
app.command("list", help="Show active scars.")(list_cmd.run)
app.command("log", help="Show recent fires.")(log_cmd.run)
app.command("stats", help="Compute persistence metrics from fires.jsonl.")(stats.run)
app.command("disable", help="Disable a scar without deleting it.")(disable.run)
app.command("doctor", help="Diagnose installation and hook wiring.")(doctor.run)
app.command("validate", help="Run Capa 4 rules over opportunities.")(validate.run)
app.command("dashboard", help="Render MD + HTML metrics dashboard.")(dashboard.run)
app.command("audit", help="Run validate + cross-link + dashboard pipeline.")(audit.run)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show fscars version and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        typer.echo(f"fscars {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
