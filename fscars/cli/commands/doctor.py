"""`fscar doctor` — diagnose installation and hook wiring."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from fscars import __version__
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
    """Run a self-check on a project and report PASS / WARN / FAIL items."""
    typer.echo(f"fscars version: {__version__}")
    typer.echo(f"project root  : {project}")
    typer.echo("")

    store = default_store(project)

    items: list[tuple[str, str, str]] = []

    items.append(
        ("PASS" if store.root.exists() else "FAIL", ".fscars/ exists", str(store.root))
    )
    items.append(
        (
            "PASS" if store.config_file.exists() else "WARN",
            "config.toml present",
            str(store.config_file),
        )
    )
    items.append(
        (
            "PASS" if store.logs_dir.exists() else "WARN",
            "logs/ directory ready",
            str(store.logs_dir),
        )
    )

    settings_path = project / ".claude" / "settings.json"
    settings_ok = False
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = settings.get("hooks") or {}
            settings_ok = any(
                isinstance(v, list)
                and any(
                    isinstance(item, dict)
                    and "fscars.run_hook" in str(item.get("command", ""))
                    for item in v
                )
                for v in hooks.values()
            )
        except json.JSONDecodeError:
            settings_ok = False
    items.append(
        (
            "PASS" if settings_ok else "WARN",
            "Claude Code hook wired",
            str(settings_path),
        )
    )

    fail = False
    for status, label, detail in items:
        color = {
            "PASS": typer.colors.GREEN,
            "WARN": typer.colors.YELLOW,
            "FAIL": typer.colors.RED,
        }.get(status, typer.colors.WHITE)
        typer.secho(f"[{status}] ", fg=color, nl=False)
        typer.echo(f"{label} — {detail}")
        if status == "FAIL":
            fail = True

    typer.echo("")
    if fail:
        typer.secho("doctor: one or more checks failed.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("doctor: all checks passed.", fg=typer.colors.GREEN)
