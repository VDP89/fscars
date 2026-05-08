"""`fscar log` — show recent fires."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fscars.core.log import read_fires
from fscars.core.store import default_store


def run(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project root.",
        file_okay=False,
        resolve_path=True,
    ),
    scar: str | None = typer.Option(
        None, "--scar", "-s", help="Filter to a single scar_id."
    ),
    session: str | None = typer.Option(
        None, "--session", help="Filter to a single session_id."
    ),
    n: int = typer.Option(20, "-n", help="Number of recent fires to show."),
) -> None:
    """Show the most recent fires from .fscars/logs/fires.jsonl."""
    store = default_store(project)
    fires = read_fires(root=store.root)

    if scar:
        fires = [f for f in fires if f.scar_id == scar]
    if session:
        fires = [f for f in fires if f.session_id == session]

    fires = fires[-n:]
    if not fires:
        typer.echo("No fires recorded yet.")
        return

    table = Table(title=f"Recent fires (showing {len(fires)})", show_lines=False)
    table.add_column("timestamp")
    table.add_column("scar_id")
    table.add_column("event")
    table.add_column("action")
    table.add_column("tool")
    table.add_column("trigger")
    table.add_column("ms", justify="right")

    for f in fires:
        table.add_row(
            f.timestamp,
            f.scar_id,
            f.event_type if isinstance(f.event_type, str) else f.event_type.value,
            f.action if isinstance(f.action, str) else f.action.value,
            f.tool_name or "-",
            (f.trigger_match or "")[:40],
            f"{f.latency_ms:.1f}" if f.latency_ms is not None else "-",
        )

    Console().print(table)
