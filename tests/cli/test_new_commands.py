"""Smoke tests for fscar validate / dashboard / audit CLI commands."""

from __future__ import annotations

import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from fscars.cli.main import app
from fscars.core.fire import Action, FireRecord, Severity
from fscars.core.log import log_fire
from fscars.core.opp_log import log_opportunity
from fscars.core.payload import HookEventType

runner = CliRunner()


def _seed_fire(root: Path, scar: str = "scar_x", trigger: str = "foo.py") -> None:
    log_fire(
        FireRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id="s1",
            project_id="p1",
            scar_id=scar,
            scar_name="X",
            scar_version="1.0.0",
            event_type=HookEventType.PRE_TOOL_USE,
            severity=Severity.WARN,
            action=Action.INJECTED,
            trigger_match=trigger,
        ),
        root=root,
    )


def _seed_opps(root: Path) -> None:
    log_opportunity(
        {"event_id": "e1", "scar_id": "scar_x", "notes": "code write 10L: a.py"},
        root=root,
    )
    log_opportunity(
        {"event_id": "e2", "scar_id": "scar_x", "notes": "code write 300L: b.py"},
        root=root,
    )


def test_dashboard_empty_project(tmp_path: Path):
    result = runner.invoke(
        app, ["dashboard", "--project", str(tmp_path), "--format", "md"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "SCARS_DASHBOARD.md").exists()


def test_dashboard_writes_html(tmp_path: Path):
    _seed_opps(tmp_path / ".fscars")
    result = runner.invoke(
        app, ["dashboard", "--project", str(tmp_path), "--format", "html"]
    )
    assert result.exit_code == 0, result.output
    html = (tmp_path / "SCARS_DASHBOARD.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html


def test_validate_without_classifiers_reports_no_op(tmp_path: Path):
    _seed_opps(tmp_path / ".fscars")
    result = runner.invoke(app, ["validate", "--project", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No classifiers" in result.output


def test_validate_with_classifiers_apply(tmp_path: Path):
    _seed_opps(tmp_path / ".fscars")

    # Drop a tiny user module that registers a line_count classifier on scar_x.
    user_mod = tmp_path / "user_clf.py"
    user_mod.write_text(
        textwrap.dedent(
            """
            from fscars.validation.rules import line_count_classifier

            def register(engine):
                engine.register("scar_x", line_count_classifier())
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        result = runner.invoke(
            app,
            [
                "validate",
                "--project",
                str(tmp_path),
                "--classifiers",
                "user_clf:register",
                "--apply",
            ],
        )
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("user_clf", None)

    assert result.exit_code == 0, result.output
    assert "Wrote" in result.output


def test_audit_dry_run(tmp_path: Path):
    _seed_opps(tmp_path / ".fscars")
    result = runner.invoke(
        app, ["audit", "--project", str(tmp_path), "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    # Dry run should not produce dashboard files
    assert not (tmp_path / "SCARS_DASHBOARD.md").exists()


def test_audit_live_writes_dashboard_and_handles_uuid_fires(tmp_path: Path):
    """Regression: FireRecord.event_id is a UUID; if serialization isn't
    JSON-mode-aware, save_opps blows up after cross-linking writes
    fire_event_id into the opportunities log.
    """
    root = tmp_path / ".fscars"
    _seed_opps(root)
    _seed_fire(root)

    result = runner.invoke(app, ["audit", "--project", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "SCARS_DASHBOARD.md").exists()
    assert (tmp_path / "SCARS_DASHBOARD.html").exists()


def test_audit_with_classifiers_applies_capa4(tmp_path: Path):
    """`fscar audit --classifiers MODULE:FUNC` runs Capa 4 over real opps,
    not the no-op path, and still writes the dashboard end to end.
    """
    _seed_opps(tmp_path / ".fscars")

    user_mod = tmp_path / "user_clf_audit.py"
    user_mod.write_text(
        textwrap.dedent(
            """
            from fscars.validation.rules import line_count_classifier

            def register(engine):
                engine.register("scar_x", line_count_classifier())
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        result = runner.invoke(
            app,
            [
                "audit",
                "--project",
                str(tmp_path),
                "--classifiers",
                "user_clf_audit:register",
            ],
        )
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("user_clf_audit", None)

    assert result.exit_code == 0, result.output
    assert "Capa 4" in result.output
    # The classifier actually ran over the seeded opps (not "0 opps classified").
    assert "0 opps classified" not in result.output
    assert (tmp_path / "SCARS_DASHBOARD.md").exists()
    assert (tmp_path / "SCARS_DASHBOARD.html").exists()


def test_dashboard_rejects_malformed_brand_json(tmp_path: Path):
    _seed_opps(tmp_path / ".fscars")
    bad = tmp_path / "brand.json"
    bad.write_text("{not valid json", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "dashboard",
            "--project",
            str(tmp_path),
            "--format",
            "html",
            "--brand",
            str(bad),
        ],
    )
    assert result.exit_code != 0
    assert "JSON" in result.output


def test_dashboard_rejects_non_object_brand(tmp_path: Path):
    _seed_opps(tmp_path / ".fscars")
    notobj = tmp_path / "brand.json"
    notobj.write_text('["#ffffff", "#000000"]', encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "dashboard",
            "--project",
            str(tmp_path),
            "--format",
            "html",
            "--brand",
            str(notobj),
        ],
    )
    assert result.exit_code != 0
    assert "object" in result.output.lower()
