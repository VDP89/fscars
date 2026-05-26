"""Unit tests for fscars.dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fscars.dashboard import (
    DEFAULT_BRAND,
    compute_metrics,
    filter_period,
    render_html,
    render_markdown,
)


def _fire(scar: str, ts: str, outcome: str | None = None) -> dict:
    f = {"scar_id": scar, "timestamp": ts}
    if outcome:
        f["outcome"] = outcome
    return f


def _opp(scar: str, ts: str, **extra) -> dict:
    return {"scar_id": scar, "timestamp": ts, **extra}


def test_filter_period_all_returns_everything():
    rows = [{"timestamp": "2026-01-01T00:00:00Z"}]
    assert filter_period(rows, "all") == rows


def test_filter_period_7d_drops_old():
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=30)).isoformat()
    recent = (now - timedelta(days=1)).isoformat()
    rows = [{"timestamp": old}, {"timestamp": recent}]
    out = filter_period(rows, "7d")
    assert out == [{"timestamp": recent}]


def test_filter_period_unknown_falls_back():
    rows = [{"timestamp": "2026-01-01T00:00:00Z"}]
    assert filter_period(rows, "weird") == rows


def test_compute_metrics_basic():
    fires = [
        _fire("scar_x", "2026-05-26T10:00:00Z", "error_prevented"),
        _fire("scar_x", "2026-05-26T10:00:01Z", "false_positive"),
        _fire("scar_y", "2026-05-26T10:00:02Z"),
    ]
    opps = [
        _opp("scar_x", "2026-05-26T10:00:00Z", validated_by="capa_4_auto", validated=True),
        _opp(
            "scar_x",
            "2026-05-26T10:00:01Z",
            validated_by="capa_3_llm_haiku",
            validated=False,
            llm_classification="ok",
        ),
        _opp("scar_y", "2026-05-26T10:00:02Z"),  # pending
    ]
    m = compute_metrics(fires, opps)
    assert m.fires_total == 3
    assert m.opps_total == 3
    assert m.capa_4 == 1
    assert m.capa_3 == 1
    assert m.pending == 1
    assert m.llm_calls == 1
    assert m.by_outcome["error_prevented"] == 1
    assert m.by_outcome["false_positive"] == 1
    assert m.by_outcome["unknown"] == 1


def test_per_scar_row_pct():
    fires = [
        _fire("scar_x", "t1", "false_positive") for _ in range(12)
    ] + [_fire("scar_x", "t2", "error_prevented")]
    m = compute_metrics(fires, [])
    row = m.per_scar[0]
    assert row.fires == 13
    assert row.fp == 12
    assert row.fp_pct == "92%"


def test_flags_warn_when_high_fp():
    fires = [_fire("scar_x", "t", "false_positive") for _ in range(20)]
    m = compute_metrics(fires, [])
    assert any("FP rate" in f for f in m.flags)


def test_flags_info_when_opps_no_fires():
    opps = [_opp("scar_x", "2026-05-26T10:00:00Z") for _ in range(3)]
    m = compute_metrics([], opps)
    assert any("0 actual fires" in f for f in m.flags)


def test_render_markdown_includes_sections():
    fires = [_fire("scar_x", "2026-05-26T10:00:00Z", "error_prevented")]
    m = compute_metrics(fires, [])
    md = render_markdown(m, title="my dash")
    assert "# my dash" in md
    assert "## Headline" in md
    assert "## Outcomes" in md
    assert "## Per scar" in md
    assert "error_prevented" in md


def test_render_html_includes_palette_overrides():
    m = compute_metrics([], [])
    html = render_html(m, brand={"primary": "#ff0000"})
    assert "#ff0000" in html
    # Defaults still present where not overridden
    assert DEFAULT_BRAND["accent"] in html


def test_render_html_self_contained():
    m = compute_metrics([], [])
    html = render_html(m)
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
    assert "<style>" in html
    assert "https://" not in html  # no CDN deps


def test_scar_id_prefix_filter():
    fires = [_fire("scar_x", "t"), _fire("session_start", "t")]
    m = compute_metrics(fires, [], scar_id_prefix="scar_")
    assert [r.scar for r in m.per_scar] == ["scar_x"]


def test_llm_cost_per_call_override():
    opps = [_opp("scar_x", "t", llm_classification="ok") for _ in range(10)]
    m = compute_metrics([], opps, llm_cost_per_call_usd=0.01)
    assert m.llm_cost_usd == 0.1
