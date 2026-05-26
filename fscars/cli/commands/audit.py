"""`fscar audit` — run the full validation pipeline end to end.

Sequence: Capa 4 (rules) → cross-link fires↔opps → render dashboard.

Capa 3 (LLM) is NOT invoked by default because it spawns external subprocess
calls and costs money. Use ``fscar validate --apply`` followed by a separate
LLM step in scripts that need it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from fscars.cli.commands._classifier_loader import load_spec
from fscars.core.log import read_fires
from fscars.core.opp_log import read_opps, save_opps
from fscars.core.store import default_store
from fscars.dashboard import (
    compute_metrics,
    filter_period,
    render_html,
    render_markdown,
)
from fscars.validation import RulesEngine, apply_decisions, cross_link_fires_opps


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
        help="MODULE:FUNC that registers Capa 4 classifiers on the engine.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Compute everything but skip disk writes."
    ),
    period: str = typer.Option(
        "all", "--period", help="Dashboard window: all, 7d, 30d, 90d."
    ),
) -> None:
    """Validate (Capa 4) + cross-link + render dashboard."""
    console = Console()
    store = default_store(project)
    fires_records = read_fires(root=store.root)
    fires_raw = [f.model_dump(mode="json") for f in fires_records]
    opps = read_opps(root=store.root)

    # --- Capa 4 ---
    engine = RulesEngine()
    if classifiers:
        load_spec(classifiers)(engine)
    decisions = engine.classify_all(opps)
    timestamp = datetime.now(timezone.utc).isoformat()
    n_classified = apply_decisions(opps, decisions, timestamp=timestamp)
    console.print(f"[cyan]Capa 4[/cyan]: {n_classified} opps classified")

    # --- Cross-link ---
    stats = cross_link_fires_opps(fires_raw, opps)
    console.print(
        f"[cyan]cross-link[/cyan]: matched={stats.matched} "
        f"unmatched={stats.unmatched}"
    )

    if not dry_run:
        save_opps(opps, root=store.root)
        console.print(f"[green]wrote[/green] {store.opps_file}")

    # --- Dashboard ---
    fires = filter_period(fires_raw, period)
    opps_period = filter_period(opps, period)
    metrics = compute_metrics(fires, opps_period, period=period)

    if not dry_run:
        md_path = project / "SCARS_DASHBOARD.md"
        html_path = project / "SCARS_DASHBOARD.html"
        md_path.write_text(render_markdown(metrics), encoding="utf-8")
        html_path.write_text(render_html(metrics), encoding="utf-8")
        console.print(f"[green]wrote[/green] {md_path}")
        console.print(f"[green]wrote[/green] {html_path}")

    console.print(
        f"[dim]fires={metrics.fires_total} opps={metrics.opps_total} "
        f"pending={metrics.pending} matched={metrics.fire_matched}[/dim]"
    )
