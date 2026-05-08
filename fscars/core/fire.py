"""Fire records — what gets logged when a Scar fires.

A Fire is the unit of observability. Every time a Scar matches and emits
output, exactly one Fire is appended to the JSONL log. Schema is versioned
so future readers can detect and migrate older entries.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from fscars.core.payload import HookEventType, HookPayload


class Severity(str, Enum):
    """How seriously the engine treats a Scar match."""

    WARN = "warn"
    BLOCK = "block"
    INFO = "info"


class Action(str, Enum):
    """What the Scar did with the matched payload."""

    INJECTED = "injected"   # additionalContext or systemMessage emitted
    BLOCKED = "blocked"     # exit code 2 (denies the tool call)
    LOGGED = "logged"       # observation only, no message emitted


SCHEMA_VERSION = 1


class FireRecord(BaseModel):
    """One JSONL line written to fires.jsonl on every Scar fire.

    The record format is the public API of the log — external readers
    (analytics, dashboards) commit to this shape.
    """

    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    schema_version: int = SCHEMA_VERSION
    timestamp: str  # ISO-8601 with timezone offset
    event_id: UUID = Field(default_factory=uuid4)
    session_id: str
    project_id: str
    scar_id: str
    scar_name: str
    scar_version: str
    event_type: HookEventType
    severity: Severity
    action: Action
    tool_name: str | None = None
    trigger_match: str = ""
    latency_ms: float | None = None
    tokens_added: int = 0
    payload_hash: str = ""
    model: str | None = None
    project_context: str | None = None
    notes: str | None = None
    fscars_version: str = ""


class Fire:
    """Helper that builds a FireRecord from a Scar + a HookPayload."""

    def __init__(
        self,
        *,
        scar_id: str,
        scar_name: str,
        scar_version: str,
        severity: Severity,
        action: Action,
        payload: HookPayload,
        trigger_match: str = "",
        tokens_added: int = 0,
        latency_ms: float | None = None,
        notes: str | None = None,
    ) -> None:
        self.scar_id = scar_id
        self.scar_name = scar_name
        self.scar_version = scar_version
        self.severity = severity
        self.action = action
        self.payload = payload
        self.trigger_match = trigger_match
        self.tokens_added = tokens_added
        self.latency_ms = latency_ms
        self.notes = notes

    def to_record(self) -> FireRecord:
        from fscars import __version__ as fscars_version

        return FireRecord(
            timestamp=_now_iso(),
            session_id=self.payload.session_id or _session_id(self.payload.cwd),
            project_id=_project_id(self.payload.cwd),
            scar_id=self.scar_id,
            scar_name=self.scar_name,
            scar_version=self.scar_version,
            event_type=self.payload.event_type,
            severity=self.severity,
            action=self.action,
            tool_name=self.payload.tool_name,
            trigger_match=self.trigger_match[:200],
            latency_ms=self.latency_ms,
            tokens_added=self.tokens_added,
            payload_hash=_hash(self.payload.content or self.trigger_match),
            model=_active_model(),
            project_context=None,
            notes=self.notes,
            fscars_version=fscars_version,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _session_id(cwd: str) -> str:
    """8-char SHA256 of cwd + UTC date — stable across a single day."""
    cwd = cwd or os.getcwd()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{cwd}|{day}".encode()).hexdigest()[:8]


def _project_id(cwd: str) -> str:
    """8-char SHA256 of the working directory — stable across sessions."""
    cwd = cwd or os.getcwd()
    return hashlib.sha256(cwd.encode()).hexdigest()[:8]


def _hash(text: str) -> str:
    text = text or ""
    return "sha256:" + hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:32]


def _active_model() -> str | None:
    """Best-effort detection of the current model.

    Returns None when we cannot tell, instead of guessing — guessing
    introduces bias into recall calculations.
    """
    for var in ("CLAUDE_MODEL", "ANTHROPIC_MODEL", "CLAUDE_CODE_MODEL"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def estimate_tokens(*chunks: str | None) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    total = 0
    for c in chunks:
        if c:
            total += len(c)
    return max(0, total // 4)


# Re-export the helpers used by adapters/tests
__all__ = [
    "SCHEMA_VERSION",
    "Action",
    "Fire",
    "FireRecord",
    "Severity",
    "estimate_tokens",
]
