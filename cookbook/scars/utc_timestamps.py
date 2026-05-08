"""Starter scar — push the agent toward UTC timestamps in handler-style code.

A canonical example from the README: time-zone bugs that reappear every
session because the model's prior is local-time-by-default.
"""

from __future__ import annotations

import re

from fscars.core.fire import Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput

LOCAL_TIME_PATTERNS = (
    re.compile(r"\btime\.Now\s*\(\s*\)"),                # Go
    re.compile(r"\bnew\s+Date\s*\(\s*\)"),               # JS/TS
    re.compile(r"\bdatetime\.now\s*\(\s*\)"),            # Python (no tz)
    re.compile(r"\bDateTime\.Now\b"),                    # C#
    re.compile(r"\bLocalDateTime\.now\s*\(\s*\)"),       # Java
)

HANDLER_HINTS = ("handler", "controller", "route", "endpoint", "api")


class UtcTimestampsScar(FunctionalScar):
    scar_id = "utc-timestamps"
    name = "Use UTC, never local time, in request handlers"
    rule = (
        "Always use UTC for timestamps in request handlers and persistence "
        "code paths. Local-time defaults reintroduce timezone bugs every "
        "time the model touches handler code."
    )
    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Write", "Edit")

    def matches(self, payload: HookPayload) -> bool:
        if not payload.file_path:
            return False
        if not any(h in payload.file_path for h in HANDLER_HINTS):
            return False
        content = payload.content
        return any(p.search(content) for p in LOCAL_TIME_PATTERNS)

    def build_output(self, payload: HookPayload) -> ScarOutput:
        return ScarOutput(
            additional_context=(
                f"[{self.scar_id}] Local-time call detected in handler-style file. "
                f"{self.rule}"
            ),
            system_message=f"{self.scar_id}: rewrite with explicit UTC",
        )


scar = UtcTimestampsScar()
