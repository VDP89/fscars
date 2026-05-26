"""`fscar dashboard` — render MD + HTML metrics summary."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from fscars.core.log import read_fires
from fscars.core.opp_log import read_opps
from fscars.core.store import default_store
from fscars.dashboard import (
    compute_metrics,
    filter_period,
    render_html,
    render_markdown,
)


def run(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project root.",
        file_okay=False,
        resolve_path=True,
    ),
    period: str = typer.Option(
        "all", "--period", help="Time window: all, 7d, 30d, 90d."
    ),
    fmt: str = typer.Option(
        "both", "--format", "-f", help="md, html, or both."
    ),
    output: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Output directory. Defaults to project root.",
        file_okay=False,
        resolve_path=True,
    ),
    title: str = typer.Option(
        "fscars dashboard", "--title", help="Header title."
    ),
    brand: Path | None = typer.Option(
        None,
        "--brand",
        help="JSON file with palette overrides (primary, accent, ...).",
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Render a metrics dashboard from fires.jsonl + opportunities.jsonl."""
    console = Console()
    store = default_store(project)
    fires_records = read_fires(root=store.root)
    fires = [f.model_dump(mode="json") for f in fires_records]
    opps = read_opps(root=store.root)

    fires = filter_period(fires, period)
    opps = filter_period(opps, period)

    metrics = compute_metrics(fires, opps, period=period)
    out_dir = output or project

    palette = None
    if brand is not None:
        palette = json.loads(brand.read_text(encoding="utf-8"))

    wrote: list[str] = []
    if fmt in ("md", "both"):
        md_path = out_dir / "SCARS_DASHBOARD.md"
        md_path.write_text(render_markdown(metrics, title=title), encoding="utf-8")
        wrote.append(str(md_path))
    if fmt in ("html", "both"):
        html_path = out_dir / "SCARS_DASHBOARD.html"
        html_path.write_text(
            render_html(metrics, title=title, brand=palette),
            encoding="utf-8",
        )
        wrote.append(str(html_path))

    for path in wrote:
        console.print(f"[green]wrote[/green] {path}")
    console.print(
        f"[dim]fires={metrics.fires_total} opps={metrics.opps_total} "
        f"pending={metrics.pending} llm_calls={metrics.llm_calls} "
        f"~${metrics.llm_cost_usd:.2f}[/dim]"
    )
