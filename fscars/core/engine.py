"""Engine — single entrypoint that processes a HookPayload through the registry.

This replaces the per-scar hook script architecture: instead of N hook files
each replicating boilerplate, settings.json wires ONE entrypoint and the
engine dispatches to whichever Scars match.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from fscars.core.fire import Fire
from fscars.core.log import log_fire
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput


@dataclass
class EngineResult:
    """Outcome of running the engine on a payload."""

    output: ScarOutput
    fires: list[Fire] = field(default_factory=list)
    matched_scars: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """Process exit code that the run_hook entry point should use."""
        return 2 if self.output.block else 0


class ScarRegistry:
    """Holds active Scar classes, indexed by event type."""

    def __init__(self) -> None:
        self._scars: list[FunctionalScar] = []

    def register(self, scar: FunctionalScar) -> None:
        self._scars.append(scar)

    def for_event(self, event_type: HookEventType) -> list[FunctionalScar]:
        return [s for s in self._scars if s.enabled and s.event_type == event_type]

    def all(self) -> list[FunctionalScar]:
        return list(self._scars)

    @classmethod
    def load_builtins(cls) -> ScarRegistry:
        """Discover and register all FunctionalScar subclasses under cookbook.scars.

        This is the default registry used by the engine when no custom
        registry is supplied. Cookbook scars opt-in by exporting an instance
        named `scar` in their module.
        """
        registry = cls()
        try:
            # We import lazily to avoid circulars at package import time.
            from cookbook import scars as scars_pkg  # type: ignore[import-not-found]
        except ImportError:
            return registry

        for module_info in pkgutil.iter_modules(scars_pkg.__path__):
            full = f"{scars_pkg.__name__}.{module_info.name}"
            try:
                module = importlib.import_module(full)
            except Exception:
                continue
            scar = getattr(module, "scar", None)
            if isinstance(scar, FunctionalScar):
                registry.register(scar)
                continue
            # Also accept a bare class export named after the module
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj is FunctionalScar:
                    continue
                if issubclass(obj, FunctionalScar) and obj.__module__ == full:
                    try:
                        registry.register(obj())
                    except TypeError:
                        # Abstract subclass or one requiring constructor args
                        continue
        return registry


def run(
    payload: HookPayload,
    *,
    registry: ScarRegistry | None = None,
    log_root: Path | None = None,
) -> EngineResult:
    """Process a payload. Returns the combined output + the fires produced.

    All matching scars run. Outputs are concatenated; if any scar blocks,
    the combined output blocks.
    """
    registry = registry or ScarRegistry.load_builtins()
    candidates = registry.for_event(payload.event_type)

    fires: list[Fire] = []
    matched: list[str] = []
    additional_context_chunks: list[str] = []
    system_messages: list[str] = []
    block = False

    for scar in candidates:
        if (
            scar.event_type in (HookEventType.PRE_TOOL_USE, HookEventType.POST_TOOL_USE)
            and not scar.applies_to_tool(payload.tool_name)
        ):
            continue
        try:
            if not scar.matches(payload):
                continue
        except Exception:
            # A buggy scar must not break the engine.
            continue

        start = time.time()
        try:
            output, fire = scar.fire(payload, start_time=start)
        except Exception:
            continue

        matched.append(scar.scar_id)
        fires.append(fire)
        if output.additional_context:
            additional_context_chunks.append(output.additional_context)
        if output.system_message:
            system_messages.append(output.system_message)
        if output.block:
            block = True

        record = fire.to_record()
        log_fire(record, root=log_root)

    combined = ScarOutput(
        additional_context="\n\n".join(additional_context_chunks),
        system_message=" | ".join(system_messages),
        block=block,
    )
    return EngineResult(output=combined, fires=fires, matched_scars=matched)


__all__ = ["EngineResult", "ScarRegistry", "run"]
