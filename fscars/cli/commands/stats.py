"""`fscar stats` — compute persistence metrics from fires.jsonl."""

from __future__ import annotations

import statistics
from collections import Counter
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
) -> None:
    """Show fire counts, average latency, and tokens added by scar."""
    store = default_store(project)
    fires = read_fires(root=store.root)

    if not fires:
        typer.echo("No fires recorded yet — nothing to compute.")
        return

    counts: Counter[str] = Counter(f.scar_id for f in fires)
    by_scar: dict[str, list[float]] = {}
    tokens_total: Counter[str] = Counter()
    blocked_total: Counter[str] = Counter()

    for f in fires:
        if f.latency_ms is not None and f.latency_ms >= 0:
            by_scar.setdefault(f.scar_id, []).append(f.latency_ms)
        tokens_total[f.scar_id] += f.tokens_added
        action_value = f.action if isinstance(f.action, str) else f.action.value
        if action_value == "blocked":
            blocked_total[f.scar_id] += 1

    table = Table(title=f"fscar stats ({len(fires)} fires)", show_lines=False)
    table.add_column("scar_id")
    table.add_column("fires", justify="right")
    table.add_column("blocked", justify="right")
    table.add_column("p50 ms", justify="right")
    table.add_column("p99 ms", justify="right")
    table.add_column("tokens added", justify="right")

    for scar_id, n_fires in counts.most_common():
        latencies = by_scar.get(scar_id, [])
        if latencies:
            p50 = f"{statistics.median(latencies):.1f}"
            p99 = (
                f"{statistics.quantiles(latencies, n=100)[98]:.1f}"
                if len(latencies) >= 100
                else f"{max(latencies):.1f}"
            )
        else:
            p50 = p99 = "-"
        table.add_row(
            scar_id,
            str(n_fires),
            str(blocked_total.get(scar_id, 0)),
            p50,
            p99,
            str(tokens_total[scar_id]),
        )

    Console().print(table)
