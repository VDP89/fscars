"""Helpers to load user-supplied classifier registrars from a module path.

The validation pipeline needs domain-specific rules (one per scar) that
fscars cannot ship. CLI commands accept a ``MODULE:FUNC`` spec; ``FUNC`` is
called with the :class:`RulesEngine` (or :class:`OutcomeMarker`) so the user
can register their callables.

Example user code::

    # myapp/scars.py
    def register_rules(engine):
        engine.register("scar_foo", my_classify_foo)
        engine.register("scar_bar", my_classify_bar)

Invoked as::

    fscar validate --classifiers myapp.scars:register_rules
"""

from __future__ import annotations

import importlib
from typing import Any


def load_spec(spec: str) -> Any:
    """Resolve ``"module.path:func_name"`` to the callable. Raises if either
    half is empty or import fails.
    """
    if ":" not in spec:
        raise ValueError(
            f"invalid spec {spec!r}: expected 'module.path:func_name'"
        )
    module_path, func_name = spec.split(":", 1)
    module_path = module_path.strip()
    func_name = func_name.strip()
    if not module_path or not func_name:
        raise ValueError(
            f"invalid spec {spec!r}: both module path and func name required"
        )
    module = importlib.import_module(module_path)
    try:
        return getattr(module, func_name)
    except AttributeError as exc:
        raise AttributeError(
            f"{module_path!r} has no attribute {func_name!r}"
        ) from exc


__all__ = ["load_spec"]
