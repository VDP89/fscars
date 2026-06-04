"""`fscar init` — wire fscars into the current project."""

from __future__ import annotations

import importlib.resources as resources
from pathlib import Path

import typer

from fscars.adapters.claude_code import ClaudeCodeAdapter
from fscars.adapters.codex import CodexAdapter
from fscars.core.store import StoreLayout, default_store

# Starter scars copied into `.fscars/scars/` on init. These are the documented
# WARN-level starters — enough to feel the system fire without being noisy.
# `import_aware_imports.py` is intentionally excluded (advanced, domain-specific;
# see docs/cookbook_import_aware.md). `_template.py` is copied so users have a
# local starting point, but the `_` prefix keeps the engine from loading it.
STARTER_SCARS = (
    "large_write_review.py",
    "utc_timestamps.py",
    "csv_encoding.py",
    "avoid_negative_framing.py",
    "subagent_coverage_report.py",
    "_template.py",
)


def scaffold_scars(store: StoreLayout) -> list[str]:
    """Copy the starter scars into the project's ``.fscars/scars/`` directory.

    Returns the filenames newly written. Existing files are left untouched so a
    user's edits survive a re-run of ``fscar init``.
    """
    store.scars_dir.mkdir(parents=True, exist_ok=True)
    try:
        source = resources.files("cookbook.scars")
    except (ModuleNotFoundError, ImportError):
        # Cookbook package not installed (broken/partial install) — wire the
        # hook anyway rather than crash init. Unexpected once shipped in the wheel.
        return []
    written: list[str] = []
    for name in STARTER_SCARS:
        dest = store.scars_dir / name
        if dest.exists():
            continue
        try:
            text = (source / name).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            # Cookbook resource missing (unexpected once shipped in the wheel) —
            # skip rather than break init.
            continue
        dest.write_text(text, encoding="utf-8")
        written.append(name)
    return written


def run(
    path: Path = typer.Argument(
        Path("."),
        help="Project root (defaults to the current directory).",
        file_okay=False,
        resolve_path=True,
    ),
    adapter: str = typer.Option(
        "claude_code",
        "--adapter",
        "-a",
        help="Which AI coding agent to wire up.",
    ),
) -> None:
    """Create .fscars/ and register the hook entrypoint with the chosen adapter."""
    project_root = path
    project_root.mkdir(parents=True, exist_ok=True)

    store = default_store(project_root)
    fresh = not store.exists()
    store.initialize()
    scaffolded = scaffold_scars(store)

    trust_hint = ""
    if adapter == "claude_code":
        ClaudeCodeAdapter().install(project_root)
        wired = ".claude/settings.json"
    elif adapter == "codex":
        CodexAdapter().install(project_root)
        wired = ".codex/hooks.json + AGENTS.md (+ .codex/fscars.json)"
        trust_hint = "Run `/hooks` in the Codex CLI once to review and trust the fscars hooks."
    else:
        raise typer.BadParameter(f"Unknown adapter: {adapter}")

    if fresh:
        typer.secho(
            f"[OK] Initialized fscars at {store.root}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.echo(f"[OK] fscars already initialized at {store.root}")
    typer.echo(f"[OK] Wired hook entry into {wired}")
    if scaffolded:
        active = [n for n in scaffolded if not n.startswith("_")]
        typer.secho(
            f"[OK] Scaffolded {len(active)} starter scars into {store.scars_dir}",
            fg=typer.colors.GREEN,
        )
    elif any(p.name != "_template.py" for p in store.scars_dir.glob("*.py")):
        typer.echo(f"[OK] Starter scars already present in {store.scars_dir}")
    else:
        # scaffold_scars found no cookbook resources to copy (broken install).
        typer.secho(
            "[!] Could not scaffold starter scars (cookbook resources "
            "unavailable). The hook is wired; add scars manually.",
            fg=typer.colors.YELLOW,
        )
    if trust_hint:
        typer.secho(f"[!] {trust_hint}", fg=typer.colors.YELLOW)
    typer.echo("")
    typer.echo("Next: run `fscar list` to see the active scars, edit or delete")
    typer.echo(f"      any under {store.scars_dir}, or copy `_template.py` to add one.")
