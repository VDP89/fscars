"""Starter scar — block 'we don't do X' framing in marketing copy.

Sanitized abstraction of scar_010 (definir_por_lo_que_somos) from the
Lucy Syndrome production case: a brand should be described by what it
does, not by what it avoids.
"""

from __future__ import annotations

import re

from fscars.core.fire import Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput, Scope

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bnot\s+(a|an|just|merely|only)\b", re.IGNORECASE), "not a/just/merely"),
    (re.compile(r"\bno es\s+(un|una)\b", re.IGNORECASE), "no es un/una (es)"),
    (re.compile(r"\bunlike\s+(other|the\s+rest)\b", re.IGNORECASE), "unlike others"),
    (re.compile(r"what\s+we\s+(don'?t|do not)\s+do", re.IGNORECASE), "what we don't do"),
    (re.compile(r"\bin\s+contrast\s+to\b", re.IGNORECASE), "in contrast to (X)"),
)

MARKETING_SCOPE = Scope(
    name_fragments=(
        "brand", "marca", "landing", "brochure", "pitch",
        "manifesto", "homepage", "about", "marketing", "copy",
    ),
    extensions=(".md", ".mdx", ".html", ".htm", ".txt"),
    excludes=("/node_modules/", "/.git/", "/dist/", "/build/"),
)


class AvoidNegativeFramingScar(FunctionalScar):
    scar_id = "avoid-negative-framing"
    name = "Marketing copy describes what the product does, not what it avoids"
    rule = (
        "Public copy should describe what the product is and does. Avoid "
        "patterns like 'we don't do X', 'unlike others', 'not just a Y'. "
        "Reframe in the affirmative before shipping."
    )
    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Write", "Edit")

    def matches(self, payload: HookPayload) -> bool:
        if not MARKETING_SCOPE.matches(payload.file_path):
            return False
        content = payload.content
        if not content:
            return False
        return any(p.search(content) for p, _ in PATTERNS)

    def build_output(self, payload: HookPayload) -> ScarOutput:
        hits: list[str] = []
        for p, label in PATTERNS:
            m = p.search(payload.content)
            if m:
                hits.append(f"{label}: \"{m.group(0)}\"")
        sample = "\n- ".join(hits[:5])
        return ScarOutput(
            additional_context=(
                f"[{self.scar_id}] Negative-framing patterns detected in marketing "
                f"copy:\n- {sample}\n\n{self.rule}"
            ),
            system_message=f"{self.scar_id}: reframe before delivering",
        )


scar = AvoidNegativeFramingScar()
