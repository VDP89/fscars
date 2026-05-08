"""Starter scar — remind the operator to self-review large code writes.

Inspired by scar_002 of the Lucy Syndrome production case.
"""

from __future__ import annotations

from fscars.core.fire import Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput

CODE_EXTENSIONS = (
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".cs",
)
LINE_THRESHOLD = 200


class LargeWriteReviewScar(FunctionalScar):
    scar_id = "large-write-review"
    name = "Large code writes deserve a self-review pass"
    rule = (
        "Before delivering a code block over 200 lines, run a self-review "
        "in three steps: (1) read the file end to end, (2) hunt bugs and "
        "edge cases, (3) confirm the diff matches the requirement."
    )
    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Write", "Edit")

    def matches(self, payload: HookPayload) -> bool:
        if not payload.file_path.endswith(CODE_EXTENSIONS):
            return False
        return payload.line_count > LINE_THRESHOLD

    def build_output(self, payload: HookPayload) -> ScarOutput:
        n = payload.line_count
        return ScarOutput(
            additional_context=(
                f"[{self.scar_id}] {n}-line code write detected. "
                f"{self.rule}"
            ),
            system_message=f"{self.scar_id}: {n}-line block — self-review before delivery",
        )

    def trigger_match(self, payload: HookPayload) -> str:
        fp = payload.file_path.rsplit("/", 1)[-1] if payload.file_path else ""
        return f"{fp} — {payload.line_count} lines"


scar = LargeWriteReviewScar()
