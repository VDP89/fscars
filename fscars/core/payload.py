"""HookPayload — normalized representation of an inbound hook event.

Each AI coding agent (Claude Code, Codex CLI, etc.) emits a different JSON
shape on its hook stdin. The adapter layer parses that shape and builds
a HookPayload, which is what the engine and Scars consume.
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HookEventType(str, Enum):
    """Canonical event types across adapters.

    Adapters map their platform-specific event names to these.
    """

    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    PERMISSION_REQUEST = "PermissionRequest"
    STOP = "Stop"
    SUBAGENT_START = "SubagentStart"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"
    POST_COMPACT = "PostCompact"
    NOTIFICATION = "Notification"


class HookPayload(BaseModel):
    """Normalized payload that Scars and the engine consume.

    Attributes
    ----------
    event_type
        Canonical event type (see HookEventType).
    tool_name
        Name of the tool being invoked (PreToolUse / PostToolUse only).
    tool_input
        Raw arguments passed to the tool. Adapter-agnostic dict.
    prompt
        Raw user prompt text (UserPromptSubmit only).
    cwd
        Working directory at the time of the event.
    session_id
        Stable identifier for this session (set by the adapter).
    raw
        The original platform-specific dict, kept for adapters that need
        to read non-standard fields.
    """

    model_config = ConfigDict(extra="ignore", frozen=False)

    event_type: HookEventType
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    prompt: str | None = None
    cwd: str = ""
    session_id: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

    # ----- Convenience accessors used by Scars -----------------------------

    @property
    def file_path(self) -> str:
        """Lowercase normalized file path from tool_input, if any."""
        raw = self.tool_input.get("file_path") or ""
        return str(raw).replace("\\", "/").lower()

    @property
    def content(self) -> str:
        """Best-effort retrieval of the content being written.

        Different tools use different keys ("content" for Write,
        "new_string" for Edit, etc.). This collapses them.
        """
        for key in ("content", "new_string", "command"):
            value = self.tool_input.get(key)
            if value:
                return str(value)
        return ""

    @property
    def line_count(self) -> int:
        """Number of newlines in the content (rough proxy for size)."""
        c = self.content
        if not c:
            return 0
        return c.count("\n") + 1

    # ----- Constructors ----------------------------------------------------

    @classmethod
    def from_stdin(cls) -> HookPayload | None:
        """Parse a JSON payload from stdin. Returns None on failure.

        This is the standard entry point for the run_hook script. Failure
        is silent on purpose: a hook must never crash the host harness.
        """
        try:
            raw = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return None
        except Exception:  # pragma: no cover — last-ditch resilience
            return None
        if not isinstance(raw, dict):
            return None
        # NB: the engine expects callers to set event_type explicitly because
        # adapter-specific names need to be normalized first. This factory
        # is only used by tests and CLI.
        try:
            return cls(**raw)
        except Exception:
            return None
