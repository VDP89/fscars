"""Store — minimal filesystem layout for a project.

A project that uses fscars has a `.fscars/` directory at its root:

    .fscars/
    ├── config.toml
    ├── scars/              # project-local scar modules (scaffolded by `fscar init`)
    │   └── *.py
    ├── logs/
    │   └── fires.jsonl
    └── disabled.txt        # optional, one scar_id per line

The hook entrypoint discovers the project's own scars under `scars/`; the
packaged cookbook is only the catalog `fscar init` copies starters from.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoreLayout:
    root: Path

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def fires_file(self) -> Path:
        return self.logs_dir / "fires.jsonl"

    @property
    def opps_file(self) -> Path:
        """Observed opportunities log (input to the validation pipeline)."""
        return self.logs_dir / "opportunities.jsonl"

    @property
    def scars_dir(self) -> Path:
        """Project-local scars directory.

        ``fscar init`` scaffolds starter scars here and the hook entrypoint
        discovers them via ``ScarRegistry.load_from_dir`` — so scars are
        per-project and editable, not global package state.
        """
        return self.root / "scars"

    @property
    def disabled_file(self) -> Path:
        return self.root / "disabled.txt"

    @property
    def config_file(self) -> Path:
        return self.root / "config.toml"

    def exists(self) -> bool:
        return self.root.exists()

    def initialize(self) -> None:
        """Create the directory layout if it does not exist yet."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            self.config_file.write_text(
                "# fscars project config\n"
                'schema_version = "1"\n',
                encoding="utf-8",
            )

    def disabled_scars(self) -> set[str]:
        if not self.disabled_file.exists():
            return set()
        return {
            line.strip()
            for line in self.disabled_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }


def default_store(cwd: Path | None = None) -> StoreLayout:
    base = cwd if cwd is not None else Path.cwd()
    return StoreLayout(root=base / ".fscars")


__all__ = ["StoreLayout", "default_store"]
