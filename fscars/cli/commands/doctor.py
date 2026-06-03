"""`fscar doctor` — diagnose installation and hook wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from fscars import __version__
from fscars.adapters.codex import CodexAdapter
from fscars.core.store import default_store


def _claude_code_items(project: Path) -> list[tuple[str, str, str]]:
    """Wiring checks for the Claude Code adapter."""
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
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            settings_ok = False
    return [
        (
            "PASS" if settings_ok else "WARN",
            "Claude Code hook wired",
            str(settings_path),
        )
    ]


def _hooks_json_events(hooks_path: Path) -> set[str]:
    """Events in .codex/hooks.json that carry an fscars command handler."""
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    if not isinstance(data, dict):
        return set()
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return set()

    wired: set[str] = set()
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list):
                continue
            if any(
                isinstance(h, dict) and "fscars.run_hook" in str(h.get("command", ""))
                for h in handlers
            ):
                wired.add(str(event))
    return wired


def _codex_items(project: Path) -> list[tuple[str, str, str]]:
    """Wiring checks for the Codex native-hooks adapter."""
    items: list[tuple[str, str, str]] = []

    hooks_path = project / CodexAdapter.HOOKS_FILE
    wired_events = _hooks_json_events(hooks_path) if hooks_path.exists() else set()
    missing = [e for e in CodexAdapter.WANTED_EVENTS if e not in wired_events]
    if hooks_path.exists() and not missing:
        status = "PASS"
        detail = str(hooks_path)
    elif hooks_path.exists():
        status = "WARN"
        detail = f"{hooks_path} (missing events: {', '.join(missing)})"
    else:
        status = "WARN"
        detail = f"{hooks_path} (not found)"
    items.append((status, "Codex native hooks registered", detail))

    manifest_path = project / CodexAdapter.MANIFEST_FILE
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            manifest = {}
    mode_ok = manifest.get("mode") == "native-hooks"
    items.append(
        (
            "PASS" if mode_ok else "WARN",
            "Codex manifest in native-hooks mode",
            str(manifest_path),
        )
    )

    agents_path = project / CodexAdapter.AGENTS_FILE
    agents_ok = (
        agents_path.exists()
        and CodexAdapter.BLOCK_START in agents_path.read_text(encoding="utf-8")
    )
    items.append(
        (
            "PASS" if agents_ok else "WARN",
            "AGENTS.md operating notes present",
            str(agents_path),
        )
    )
    return items


def run(
    project: Path = typer.Option(
        Path("."),
        "--project",
        "-p",
        help="Project root.",
        file_okay=False,
        resolve_path=True,
    ),
    adapter: str = typer.Option(
        "claude_code",
        "--adapter",
        "-a",
        help="Which adapter's wiring to check (claude_code or codex).",
    ),
) -> None:
    """Run a self-check on a project and report PASS / WARN / FAIL items."""
    typer.echo(f"fscars version: {__version__}")
    typer.echo(f"project root  : {project}")
    typer.echo(f"adapter       : {adapter}")
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

    if adapter == "codex":
        items.extend(_codex_items(project))
    elif adapter == "claude_code":
        items.extend(_claude_code_items(project))
    else:
        raise typer.BadParameter(f"Unknown adapter: {adapter}")

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
