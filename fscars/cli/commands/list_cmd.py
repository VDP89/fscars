"""`fscar list` — show registered scars and their fire counts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fscars.core.engine import ScarRegistry
from fscars.core.log import read_fires
from fscars.core.store import default_store


def run(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project root (defaults to the current directory).",
        file_okay=False,
        resolve_path=True,
    ),
) -> None:
    """List active scars with last-fire timestamps."""
    registry = ScarRegistry.load_builtins()
    store = default_store(project)

    fires = read_fires(root=store.root)
    counts: Counter[str] = Counter(f.scar_id for f in fires)
    last_fire: dict[str, str] = {}
    for f in fires:
        last_fire.setdefault(f.scar_id, f.timestamp)
        if f.timestamp > last_fire[f.scar_id]:
            last_fire[f.scar_id] = f.timestamp

    table = Table(title="Functional Scars", show_lines=False)
    table.add_column("scar_id")
    table.add_column("name")
    table.add_column("event")
    table.add_column("severity")
    table.add_column("fires", justify="right")
    table.add_column("last fire")
    table.add_column("enabled")

    scars = registry.all()
    if not scars:
        typer.echo("No scars registered. Add one in cookbook/scars/.")
        return

    for scar in scars:
        table.add_row(
            scar.scar_id,
            scar.name or "-",
            scar.event_type.value,
            scar.severity.value,
            str(counts.get(scar.scar_id, 0)),
            last_fire.get(scar.scar_id, "-"),
            "yes" if scar.enabled else "no",
        )
    Console().print(table)
