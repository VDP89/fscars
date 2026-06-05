"""Functional Scars — bolt-on correction primitive for AI coding agents.

Reference implementation of the framework described in
*Lucy Syndrome in LLM Agents: A Practitioner Framework for Cross-Session
Correction Persistence* (Del Puerto, 2026), DOI 10.5281/zenodo.19555971.
"""

from fscars.core.fire import Fire, FireRecord, Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, Scope

__version__ = "0.8.0"

__all__ = [
    "Fire",
    "FireRecord",
    "FunctionalScar",
    "HookEventType",
    "HookPayload",
    "Scope",
    "Severity",
    "__version__",
]
