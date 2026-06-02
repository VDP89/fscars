"""Adapter base class.

Each adapter wraps one AI coding agent platform (Claude Code, Codex CLI,
Cursor, etc.). The adapter knows:

- How to parse that platform's hook stdin payload.
- How to write the platform's settings/config so a single fscars entrypoint
  receives every hook event.
- How to format the output the platform expects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from fscars.core.payload import HookPayload
from fscars.core.scar import ScarOutput


class Adapter(ABC):
    """Common interface for platform adapters."""

    name: str = "abstract"

    @abstractmethod
    def parse_stdin(self, raw: dict[str, Any]) -> HookPayload | None:
        """Translate a platform-specific JSON payload into a HookPayload.

        Returns None if the payload is malformed. The engine treats None
        as "do nothing".
        """
        ...

    @abstractmethod
    def emit_output(self, output: ScarOutput) -> str:
        """Serialize ScarOutput in the format the platform expects on stdout."""
        ...

    @abstractmethod
    def install(self, project_root: Path) -> None:
        """Wire the entrypoint into the platform's hook config under project_root."""
        ...

    @abstractmethod
    def uninstall(self, project_root: Path) -> None:
        """Reverse install — remove the entrypoint registration."""
        ...


__all__ = ["Adapter"]
