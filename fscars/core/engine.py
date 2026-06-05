"""Engine — single entrypoint that processes a HookPayload through the registry.

This replaces the per-scar hook script architecture: instead of N hook files
each replicating boilerplate, settings.json wires ONE entrypoint and the
engine dispatches to whichever Scars match.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import inspect
import pkgutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

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

    def _register_module_scars(self, module: ModuleType, full_name: str) -> None:
        """Register the scars a single module exposes.

        Prefers a module-level ``scar`` instance; otherwise instantiates any
        concrete ``FunctionalScar`` subclass *defined in* that module. Shared
        by :meth:`load_builtins` (import-based) and :meth:`load_from_dir`
        (file-path based) so both discovery paths behave identically.

        A scar with an empty ``scar_id`` is never registered: that is a base or
        template class (e.g. ``ImportAwareWriteScar``), not a real scar, and
        registering it would surface a blank, id-less row in ``fscar list``.
        """
        scar = getattr(module, "scar", None)
        if isinstance(scar, FunctionalScar):
            if scar.scar_id:
                self.register(scar)
            return
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is FunctionalScar:
                continue
            if issubclass(obj, FunctionalScar) and obj.__module__ == full_name:
                try:
                    instance = obj()
                except TypeError:
                    # Abstract subclass or one requiring constructor args
                    continue
                if instance.scar_id:
                    self.register(instance)

    @classmethod
    def load_builtins(cls) -> ScarRegistry:
        """Discover and register all FunctionalScar subclasses under cookbook.scars.

        This is the catalog of starter scars shipped with the package. It only
        works when ``cookbook`` is importable (source checkout or a wheel that
        ships it). The runtime hook entrypoint does NOT use this — it loads the
        project's own ``.fscars/scars/`` directory via :meth:`load_from_dir`, so
        scars are per-project and opt-in rather than firing globally.
        """
        registry = cls()
        try:
            # We import lazily to avoid circulars at package import time.
            from cookbook import scars as scars_pkg
        except ImportError:
            return registry

        for module_info in pkgutil.iter_modules(scars_pkg.__path__):
            full = f"{scars_pkg.__name__}.{module_info.name}"
            try:
                module = importlib.import_module(full)
            except Exception:
                continue
            registry._register_module_scars(module, full)
        return registry

    @classmethod
    def load_from_dir(cls, scars_dir: Path) -> ScarRegistry:
        """Discover scars from ``*.py`` files in a project's scars directory.

        Loads each module by file path (no package import required), so it works
        in a plain ``pip install fscars`` environment where ``cookbook`` is not
        on the import path. Files whose names start with ``_`` (e.g. the copied
        ``_template.py``) are skipped. A module that fails to import is skipped
        rather than breaking the whole hook run.
        """
        registry = cls()
        if not scars_dir.is_dir():
            return registry

        for path in sorted(scars_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            # Path-unique synthetic name: two projects may have a scar file with
            # the same stem, and the module MUST be in sys.modules before
            # exec_module so machinery that resolves `sys.modules[__module__]`
            # (e.g. a module-level @dataclass) works — otherwise the module
            # silently fails to import and the scar is never registered.
            digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
            mod_name = f"_fscars_project_scar_{path.stem}_{digest}"
            try:
                spec = importlib.util.spec_from_file_location(mod_name, path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(mod_name, None)
                continue
            registry._register_module_scars(module, mod_name)
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

    The caller chooses the registry: the hook entrypoint passes the project's
    own ``.fscars/scars/`` (``ScarRegistry.load_from_dir``). When no registry is
    supplied the engine runs an **empty** one — it never auto-loads the packaged
    cookbook, so importing ``fscars`` cannot surprise-fire global scars. Pass
    ``ScarRegistry.load_builtins()`` explicitly to run the shipped catalog.
    """
    registry = registry if registry is not None else ScarRegistry()
    candidates = registry.for_event(payload.event_type)

    fires: list[Fire] = []
    matched: list[str] = []
    additional_context_chunks: list[str] = []
    system_messages: list[str] = []
    block = False

    for scar in candidates:
        if (
            scar.event_type
            in (
                HookEventType.PRE_TOOL_USE,
                HookEventType.POST_TOOL_USE,
                HookEventType.PERMISSION_REQUEST,
            )
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
