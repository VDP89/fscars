"""FunctionalScar — base class for every scar definition."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from fscars.core.fire import Action, Fire, Severity, estimate_tokens
from fscars.core.payload import HookEventType, HookPayload


@dataclass(frozen=True)
class ScarOutput:
    """What a Scar emits when it fires.

    Attributes
    ----------
    additional_context
        Text injected as `additionalContext` in the hook output.
    system_message
        Short marker shown to the operator (Claude Code surface).
    block
        If True, the engine emits exit code 2 (denies the tool call).
    """

    additional_context: str = ""
    system_message: str = ""
    block: bool = False

    @property
    def is_empty(self) -> bool:
        return not (self.additional_context or self.system_message or self.block)


@dataclass(frozen=True)
class Scope:
    """Path/name/extension filter shared across Scars that target the same domain.

    Empty fields mean "no filter on that axis" — the test passes vacuously.
    """

    path_fragments: tuple[str, ...] = ()
    name_fragments: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()

    def matches(self, file_path: str) -> bool:
        if not file_path:
            return not (self.path_fragments or self.name_fragments or self.extensions)
        if self.excludes and any(ex in file_path for ex in self.excludes):
            return False
        if self.extensions and not file_path.endswith(self.extensions):
            return False
        if self.path_fragments or self.name_fragments:
            in_path = self.path_fragments and any(f in file_path for f in self.path_fragments)
            in_name = self.name_fragments and any(f in file_path for f in self.name_fragments)
            if not (in_path or in_name):
                return False
        return True


class FunctionalScar(ABC):
    """Base class. Concrete scars subclass this and implement matches/build_output.

    Class attributes are the metadata the engine uses to filter, log, and
    surface the scar. Subclasses override them as plain class attributes.
    """

    # Identity
    scar_id: str = ""
    name: str = ""
    rule: str = ""
    version: str = "1.0.0"

    # Behavior
    severity: Severity = Severity.WARN
    event_type: HookEventType = HookEventType.PRE_TOOL_USE
    tool_matchers: tuple[str, ...] = ()  # only used for PreToolUse / PostToolUse
    enabled: bool = True

    # ----- API the engine calls -------------------------------------------

    @abstractmethod
    def matches(self, payload: HookPayload) -> bool:
        """Return True iff this scar wants to fire for the given payload."""
        ...

    @abstractmethod
    def build_output(self, payload: HookPayload) -> ScarOutput:
        """Build the message emitted to the host harness."""
        ...

    # ----- Default helpers (subclasses rarely override these) -------------

    def trigger_match(self, payload: HookPayload) -> str:
        """Short fragment that explains why this scar fired.

        Default: filename + first 60 chars of content. Override for richer
        signals (e.g. matched regex group).
        """
        fp = payload.file_path.rsplit("/", 1)[-1] if payload.file_path else ""
        head = (payload.content or "")[:60].replace("\n", " ")
        if fp and head:
            return f"{fp} — {head}"
        return fp or head or payload.tool_name or payload.event_type.value

    def fire(self, payload: HookPayload, *, start_time: float | None = None) -> tuple[ScarOutput, Fire]:
        """Run the scar end-to-end: build output + create a Fire record.

        The engine logs the Fire and emits the output.
        """
        output = self.build_output(payload)
        latency_ms: float | None = None
        if start_time is not None:
            latency_ms = round((time.time() - start_time) * 1000.0, 2)

        action = Action.BLOCKED if output.block else (
            Action.INJECTED if not output.is_empty else Action.LOGGED
        )

        fire_record = Fire(
            scar_id=self.scar_id,
            scar_name=self.name or self.scar_id,
            scar_version=self.version,
            severity=Severity.BLOCK if output.block else self.severity,
            action=action,
            payload=payload,
            trigger_match=self.trigger_match(payload),
            tokens_added=estimate_tokens(output.additional_context, output.system_message),
            latency_ms=latency_ms,
        )
        return output, fire_record

    # ----- Helpers used by subclasses --------------------------------------

    @classmethod
    def applies_to_event(cls, event_type: HookEventType) -> bool:
        return cls.event_type == event_type

    @classmethod
    def applies_to_tool(cls, tool_name: str | None) -> bool:
        if not cls.tool_matchers:
            return True
        if not tool_name:
            return False
        return tool_name in cls.tool_matchers


__all__ = ["FunctionalScar", "ScarOutput", "Scope"]
