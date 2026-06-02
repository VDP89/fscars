"""Markdown + HTML dashboard generator for the validation pipeline.

Renders a single-page summary of fires and opportunities so an operator can
audit the system without running five separate scripts. Two outputs share
the same metrics:

* :func:`render_markdown` for terminal-friendly review and pasting into
  changelogs or issues.
* :func:`render_html` for browser viewing (self-contained, no CDN).

The palette is parametric so deployments can override it for their brand.
:data:`DEFAULT_BRAND` ships a neutral slate-and-blue scheme.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_BRAND: dict[str, str] = {
    "primary": "#1e293b",
    "background": "#f8fafc",
    "accent": "#3b82f6",
    "secondary": "#475569",
    "ok": "#16a34a",
    "warn": "#d97706",
    "danger": "#dc2626",
    "muted": "#94a3b8",
}

_PERIOD_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}


def _parse_ts(ts: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def filter_period(rows: Iterable[dict[str, Any]], period: str) -> list[dict[str, Any]]:
    """Return rows whose ``timestamp`` falls within the named window.

    ``period`` is one of ``"all"``, ``"7d"``, ``"30d"``, ``"90d"``. Anything
    else falls back to ``all``. Rows without a parseable timestamp are
    dropped when filtering, kept when ``period == "all"``.
    """
    rows = list(rows)
    if period == "all":
        return rows
    days = _PERIOD_DAYS.get(period, 0)
    if not days:
        return rows
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for r in rows:
        ts = _parse_ts(r.get("timestamp", ""))
        if ts is not None and ts >= cutoff:
            out.append(r)
    return out


@dataclass
class ScarRow:
    scar: str
    fires: int
    opps: int
    matched: int
    prev: int
    fp: int
    unk: int

    @property
    def fp_pct(self) -> str:
        return f"{100 * self.fp / self.fires:.0f}%" if self.fires else "n/a"

    @property
    def prev_pct(self) -> str:
        return f"{100 * self.prev / self.fires:.0f}%" if self.fires else "n/a"


@dataclass
class DashboardMetrics:
    period: str
    fires_total: int
    opps_total: int
    capa_4: int
    capa_3: int
    pending: int
    fire_matched: int
    file_not_found: int
    llm_calls: int
    llm_cost_usd: float
    by_outcome: dict[str, int] = field(default_factory=dict)
    per_scar: list[ScarRow] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def compute_metrics(
    fires: list[dict[str, Any]],
    opps: list[dict[str, Any]],
    *,
    period: str = "all",
    scar_id_field: str = "scar_id",
    scar_id_prefix: str = "scar_",
    llm_cost_per_call_usd: float = 0.0015,
) -> DashboardMetrics:
    """Crunch fires + opps into the dashboard's headline + per-scar rows.

    Args:
        fires, opps: Already period-filtered rows.
        period: Period label for display.
        scar_id_prefix: Only scars whose id starts with this prefix appear
            in the per-scar table. Set to ``""`` to include every scar.
        llm_cost_per_call_usd: Used to estimate cumulative LLM cost from
            ``llm_classification == "ok"`` rows. Default matches Haiku
            ballpark; override for other models.
    """
    by_outcome = Counter(f.get("outcome", "unknown") for f in fires)

    capa_4 = sum(1 for o in opps if o.get("validated_by") == "capa_4_auto")
    capa_3 = sum(
        1 for o in opps
        if str(o.get("validated_by", "")).startswith("capa_3_llm")
    )
    pending = sum(1 for o in opps if o.get("validated") is None)
    fire_matched = sum(1 for o in opps if o.get("fire_matched"))
    file_not_found = sum(
        1 for o in opps if o.get("llm_classification") == "skipped_file_not_found"
    )
    llm_calls = sum(1 for o in opps if o.get("llm_classification") == "ok")
    llm_cost = llm_calls * llm_cost_per_call_usd

    scars = sorted(
        {f.get(scar_id_field, "") for f in fires}
        | {o.get(scar_id_field, "") for o in opps}
    )
    if scar_id_prefix:
        scars = [s for s in scars if s and s.startswith(scar_id_prefix)]

    per_scar: list[ScarRow] = []
    for s in scars:
        s_fires = [f for f in fires if f.get(scar_id_field) == s]
        s_opps = [o for o in opps if o.get(scar_id_field) == s]
        per_scar.append(
            ScarRow(
                scar=s,
                fires=len(s_fires),
                opps=len(s_opps),
                matched=sum(1 for o in s_opps if o.get("fire_matched")),
                prev=sum(1 for f in s_fires if f.get("outcome") == "error_prevented"),
                fp=sum(1 for f in s_fires if f.get("outcome") == "false_positive"),
                unk=sum(
                    1 for f in s_fires
                    if f.get("outcome") in (None, "unknown")
                ),
            )
        )

    flags = _build_flags(per_scar)

    return DashboardMetrics(
        period=period,
        fires_total=len(fires),
        opps_total=len(opps),
        capa_4=capa_4,
        capa_3=capa_3,
        pending=pending,
        fire_matched=fire_matched,
        file_not_found=file_not_found,
        llm_calls=llm_calls,
        llm_cost_usd=llm_cost,
        by_outcome=dict(by_outcome),
        per_scar=per_scar,
        flags=flags,
    )


def _build_flags(per_scar: list[ScarRow]) -> list[str]:
    flags: list[str] = []
    for row in per_scar:
        if row.fires > 10 and row.fp_pct != "n/a":
            n = int(row.fp_pct.rstrip("%"))
            if n >= 50:
                flags.append(
                    f"WARN {row.scar}: FP rate {row.fp_pct} (>=50%) over "
                    f"{row.fires} fires. Review heuristic or hook."
                )
        if row.fires == 0 and row.opps > 0:
            flags.append(
                f"INFO {row.scar}: {row.opps} opportunities observed but "
                f"0 actual fires. Hook may be misconfigured."
            )
    return flags


def _color_fp(pct_str: str, brand: dict[str, str]) -> str:
    if pct_str == "n/a":
        return brand["muted"]
    try:
        n = int(pct_str.rstrip("%"))
    except ValueError:
        return brand["muted"]
    if n >= 50:
        return brand["danger"]
    if n >= 20:
        return brand["warn"]
    return brand["ok"]


def _color_prev(pct_str: str, brand: dict[str, str]) -> str:
    if pct_str == "n/a":
        return brand["muted"]
    try:
        n = int(pct_str.rstrip("%"))
    except ValueError:
        return brand["muted"]
    if n >= 80:
        return brand["ok"]
    if n >= 40:
        return brand["warn"]
    return brand["danger"]


def render_markdown(
    metrics: DashboardMetrics,
    *,
    title: str = "fscars dashboard",
    generated_at: str | None = None,
) -> str:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).astimezone().isoformat()

    lines: list[str] = [
        f"# {title} ({metrics.period})",
        "",
        f"_Generated: {generated_at}_",
        "",
        "## Headline",
        "",
        f"- **Total fires** ({metrics.period}): {metrics.fires_total}",
        f"- **Total opportunities** ({metrics.period}): {metrics.opps_total}",
        f"- **Validated by Capa 4 (rules)**: {metrics.capa_4}",
        f"- **Validated by Capa 3 (LLM)**: {metrics.capa_3}",
        f"- **Pending validation**: {metrics.pending}",
        f"- **Skipped file_not_found**: {metrics.file_not_found}",
        f"- **Fire matched (cross-link)**: {metrics.fire_matched}",
        f"- **LLM calls**: {metrics.llm_calls} "
        f"(~${metrics.llm_cost_usd:.2f} USD est.)",
        "",
        "## Outcomes",
        "",
        "| outcome | count |",
        "|---|---:|",
    ]
    for k in (
        "error_prevented",
        "false_positive",
        "error_repeated",
        "error_despite_fire",
        "unknown",
    ):
        lines.append(f"| {k} | {metrics.by_outcome.get(k, 0)} |")
    lines.append("")

    lines += [
        "## Per scar",
        "",
        "| scar | fires | opps | matched | prev | fp | unk | fp% | prev% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in metrics.per_scar:
        lines.append(
            f"| {r.scar} | {r.fires} | {r.opps} | {r.matched} | "
            f"{r.prev} | {r.fp} | {r.unk} | {r.fp_pct} | {r.prev_pct} |"
        )
    lines.append("")

    if metrics.flags:
        lines += ["## Health flags", ""]
        lines += [f"- {f}" for f in metrics.flags]
        lines.append("")
    else:
        lines += ["## Health flags", "", "_None — all green._", ""]

    return "\n".join(lines)


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} ({period})</title>
<style>
  :root {{
    --primary: {primary};
    --background: {background};
    --accent: {accent};
    --secondary: {secondary};
    --ok: {ok};
    --warn: {warn};
    --danger: {danger};
    --muted: {muted};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--primary); background: var(--background);
    line-height: 1.5;
  }}
  header {{
    background: var(--primary); color: var(--background);
    padding: 1.5rem 2rem;
    border-bottom: 4px solid var(--accent);
  }}
  header h1 {{ margin: 0; font-size: 1.5rem; font-weight: 600; letter-spacing: -0.01em; }}
  header .meta {{ font-size: 0.85rem; opacity: 0.7; margin-top: 0.25rem; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
  h2 {{
    font-size: 1.15rem; margin-top: 2rem; margin-bottom: 0.75rem;
    padding-bottom: 0.4rem; border-bottom: 2px solid var(--secondary);
    color: var(--primary); font-weight: 600;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
  }}
  .card {{
    background: white;
    border: 1px solid #e2e8f0;
    border-left: 4px solid var(--accent);
    border-radius: 4px;
    padding: 1rem 1.25rem;
  }}
  .card .label {{
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--secondary); margin-bottom: 0.25rem;
  }}
  .card .value {{
    font-size: 1.5rem; font-weight: 700; color: var(--primary);
    font-variant-numeric: tabular-nums;
  }}
  .card .sub {{ font-size: 0.8rem; color: var(--muted); margin-top: 0.15rem; }}
  table {{
    border-collapse: collapse; width: 100%; background: white;
    border: 1px solid #e2e8f0; border-radius: 4px; overflow: hidden;
    font-variant-numeric: tabular-nums;
  }}
  th {{
    background: var(--primary); color: var(--background);
    text-align: left; padding: 0.6rem 0.8rem;
    font-size: 0.8rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em;
  }}
  td {{
    padding: 0.55rem 0.8rem; border-bottom: 1px solid #f1f5f9;
    font-size: 0.9rem;
  }}
  td.num {{ text-align: right; }}
  code {{
    font-family: "SF Mono", Consolas, Monaco, monospace;
    background: var(--background); padding: 0.15rem 0.35rem; border-radius: 3px;
    font-size: 0.85em;
  }}
  ul.flags li {{ margin: 0.4rem 0; }}
  .muted {{ color: var(--muted); font-style: italic; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">period: {period} — generated: {generated_at}</div>
</header>
<main>

<h2>Headline</h2>
<div class="grid">
  <div class="card"><div class="label">Total fires</div><div class="value">{fires_total}</div></div>
  <div class="card"><div class="label">Total opportunities</div><div class="value">{opps_total}</div></div>
  <div class="card"><div class="label">Capa 4 (rules)</div><div class="value">{capa_4}</div><div class="sub">deterministic auto-resolved</div></div>
  <div class="card"><div class="label">Capa 3 (LLM)</div><div class="value">{capa_3}</div><div class="sub">~${llm_cost_usd:.2f} USD est.</div></div>
  <div class="card"><div class="label">Pending</div><div class="value">{pending}</div><div class="sub">{file_not_found} file_not_found</div></div>
  <div class="card"><div class="label">Fire matched</div><div class="value">{fire_matched}</div><div class="sub">cross-link opps↔fires</div></div>
</div>

<h2>Outcomes</h2>
<table>
  <thead><tr><th>outcome</th><th style='text-align:right'>count</th></tr></thead>
  <tbody>
{rows_outcome}
  </tbody>
</table>

<h2>Per scar</h2>
<table>
  <thead>
    <tr>
      <th>scar</th><th class='num'>fires</th><th class='num'>opps</th><th class='num'>matched</th>
      <th class='num'>prev</th><th class='num'>fp</th><th class='num'>unk</th>
      <th class='num'>fp%</th><th class='num'>prev%</th>
    </tr>
  </thead>
  <tbody>
{rows_scar}
  </tbody>
</table>

<h2>Health flags</h2>
{flags_html}

</main>
</body>
</html>
"""


def render_html(
    metrics: DashboardMetrics,
    *,
    title: str = "fscars dashboard",
    generated_at: str | None = None,
    brand: dict[str, str] | None = None,
) -> str:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).astimezone().isoformat()
    palette = {**DEFAULT_BRAND, **(brand or {})}

    rows_outcome = "\n".join(
        f"    <tr><td>{k}</td>"
        f"<td style='text-align:right'>{metrics.by_outcome.get(k, 0)}</td></tr>"
        for k in (
            "error_prevented",
            "false_positive",
            "error_repeated",
            "error_despite_fire",
            "unknown",
        )
    )

    rows_scar = "\n".join(
        f"    <tr>"
        f"<td><code>{r.scar}</code></td>"
        f"<td class='num'>{r.fires}</td>"
        f"<td class='num'>{r.opps}</td>"
        f"<td class='num'>{r.matched}</td>"
        f"<td class='num'>{r.prev}</td>"
        f"<td class='num'>{r.fp}</td>"
        f"<td class='num'>{r.unk}</td>"
        f"<td class='num' style='color:{_color_fp(r.fp_pct, palette)};"
        f"font-weight:600'>{r.fp_pct}</td>"
        f"<td class='num' style='color:{_color_prev(r.prev_pct, palette)};"
        f"font-weight:600'>{r.prev_pct}</td>"
        f"</tr>"
        for r in metrics.per_scar
    )

    if metrics.flags:
        items = "".join(f"  <li>{f}</li>\n" for f in metrics.flags)
        flags_html = f"<ul class='flags'>\n{items}</ul>"
    else:
        flags_html = "<p class='muted'>None — all green.</p>"

    return _HTML_TEMPLATE.format(
        title=title,
        period=metrics.period,
        generated_at=generated_at,
        rows_outcome=rows_outcome,
        rows_scar=rows_scar,
        flags_html=flags_html,
        fires_total=metrics.fires_total,
        opps_total=metrics.opps_total,
        capa_4=metrics.capa_4,
        capa_3=metrics.capa_3,
        pending=metrics.pending,
        fire_matched=metrics.fire_matched,
        file_not_found=metrics.file_not_found,
        llm_cost_usd=metrics.llm_cost_usd,
        **palette,
    )


__all__ = [
    "DEFAULT_BRAND",
    "DashboardMetrics",
    "ScarRow",
    "compute_metrics",
    "filter_period",
    "render_html",
    "render_markdown",
]
