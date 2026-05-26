"""`fscar validate` — run Capa 4 deterministic rules over opportunities.

Optionally chains Capa 3 (LLM) over rows that Capa 4 leaves ambiguous.

The deterministic rules live in user code: pass ``--classifiers
module.path:register_func`` and that function will be invoked with a
:class:`RulesEngine` instance to register one classifier per scar.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fscars.cli.commands._classifier_loader import load_spec
from fscars.core.opp_log import read_opps, save_opps
from fscars.core.store import default_store
from fscars.validation import RulesEngine, apply_decisions
from fscars.validation.rules import summarize


def run(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project root.",
        file_okay=False,
        resolve_path=True,
    ),
    classifiers: str | None = typer.Option(
        None,
        "--classifiers",
        "-c",
        help="MODULE:FUNC that registers per-scar classifiers on the engine.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write decisions back to opportunities.jsonl. Default is dry-run.",
    ),
    scar: str | None = typer.Option(
        None, "--scar", "-s", help="Filter to a single scar_id."
    ),
) -> None:
    """Apply Capa 4 deterministic rules to opportunities."""
    console = Console()
    store = default_store(project)
    opps = read_opps(root=store.root)

    if scar:
        opps = [o for o in opps if o.get("scar_id") == scar]

    if not opps:
        console.print("[yellow]No opportunities to classify.[/yellow]")
        return

    engine = RulesEngine()
    if classifiers:
        register = load_spec(classifiers)
        register(engine)
    if not engine.classifiers:
        console.print(
            "[yellow]No classifiers registered.[/yellow] "
            "Pass --classifiers MODULE:FUNC. Reporting raw counts only."
        )

    decisions = engine.classify_all(opps)
    stats = summarize(opps, decisions)

    table = Table(title=f"fscar validate ({len(opps)} opps)", show_lines=False)
    table.add_column("scar")
    table.add_column("auto_tp", justify="right")
    table.add_column("auto_fp", justify="right")
    table.add_column("ambiguous", justify="right")
    table.add_column("no_classifier", justify="right")
    table.add_column("already", justify="right")

    for scar_id in sorted(stats.keys()):
        s = stats[scar_id]
        table.add_row(
            scar_id,
            str(s["auto_tp"]),
            str(s["auto_fp"]),
            str(s["ambiguous"]),
            str(s["no_classifier"]),
            str(s["already_validated"]),
        )
    console.print(table)

    if not apply:
        console.print(
            "[dim]Dry-run only. Use --apply to write decisions to disk.[/dim]"
        )
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    n = apply_decisions(opps, decisions, timestamp=timestamp)
    save_opps(opps, root=store.root)
    console.print(f"[green]Wrote {n} classifications to {store.opps_file}[/green]")
