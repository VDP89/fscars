"""Starter scar — remind the operator to ask subagents for a coverage report.

Sanitized abstraction of scar_005 from the Lucy Syndrome production case.
Subagent batches frequently silently drop items; asking the subagent to
enumerate what it processed surfaces the gap.
"""

from __future__ import annotations

from fscars.core.fire import Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput


class SubagentCoverageReportScar(FunctionalScar):
    scar_id = "subagent-coverage-report"
    name = "Ask subagents for a coverage report"
    rule = (
        "When dispatching a subagent over a batch (files, items, tasks), "
        "ask the prompt to end with a coverage report: which items were "
        "processed and which were skipped. Silent drop is the default "
        "failure mode."
    )
    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Task",)

    def matches(self, payload: HookPayload) -> bool:
        return payload.tool_name == "Task"

    def build_output(self, payload: HookPayload) -> ScarOutput:
        return ScarOutput(
            additional_context=(
                f"[{self.scar_id}] Dispatching a subagent. {self.rule}"
            ),
            system_message=f"{self.scar_id}: include 'BATCH COVERAGE' in the prompt",
        )


scar = SubagentCoverageReportScar()
